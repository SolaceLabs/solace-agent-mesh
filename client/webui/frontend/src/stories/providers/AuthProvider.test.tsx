/**
 * Tests for AuthProvider proactive refresh lifecycle integration.
 */
import React, { useContext } from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import * as matchers from "@testing-library/jest-dom/matchers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { MockConfigProvider } from "@/stories/mocks/MockConfigProvider";
import { CsrfContext, type CsrfContextValue } from "@/lib/contexts/CsrfContext";
import { AuthContext } from "@/lib/contexts/AuthContext";
import { AuthProvider } from "@/lib/providers/AuthProvider";
import * as apiClientModule from "@/lib/api/client";
import { sessionKeys } from "@/lib/api/sessions/keys";
import { shareKeys } from "@/lib/api/share/keys";

expect.extend(matchers);

// Helper: create a minimal JWT with a given exp (seconds since epoch)
function makeJwt(exp: number): string {
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({ exp, sub: "test-user", email: "test@example.com" }));
    return `${header}.${payload}.fake-signature`;
}

// MSW server for API mocking
const server = setupServer();

// Mock CsrfProvider
const mockCsrfValue: CsrfContextValue = {
    fetchCsrfToken: vi.fn().mockResolvedValue("test-csrf"),
    clearCsrfToken: vi.fn(),
};

function MockCsrfProvider({ children }: { children: React.ReactNode }) {
    return <CsrfContext.Provider value={mockCsrfValue}>{children}</CsrfContext.Provider>;
}

// Test component that consumes AuthContext
function AuthConsumer() {
    const ctx = useContext(AuthContext);
    if (!ctx) return <div>No context</div>;
    return (
        <div>
            <span data-testid="authenticated">{String(ctx.isAuthenticated)}</span>
            <span data-testid="useAuth">{String(ctx.useAuthorization)}</span>
            <button data-testid="logout-btn" onClick={ctx.logout}>
                Logout
            </button>
        </div>
    );
}

// Wrapper with all required providers. Accepts an optional shared QueryClient
// so tests can pre-populate cache state and assert against it post-logout.
function TestWrapper({ children, useAuthorization = true, queryClient }: { children: React.ReactNode; useAuthorization?: boolean; queryClient?: QueryClient }) {
    const client = queryClient ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return (
        <QueryClientProvider client={client}>
            <MockConfigProvider
                mockValues={{
                    configUseAuthorization: useAuthorization,
                    configAuthLoginUrl: "http://localhost:3000/api/v1/auth/login",
                    webuiServerUrl: "http://localhost:3000",
                }}
            >
                <MockCsrfProvider>
                    <AuthProvider>{children}</AuthProvider>
                </MockCsrfProvider>
            </MockConfigProvider>
        </QueryClientProvider>
    );
}

beforeAll(() => {
    server.listen({ onUnhandledRequest: "bypass" });
});

let scheduleSpy: ReturnType<typeof vi.spyOn>;
let cancelSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    (mockCsrfValue.fetchCsrfToken as ReturnType<typeof vi.fn>).mockClear();
    (mockCsrfValue.clearCsrfToken as ReturnType<typeof vi.fn>).mockClear();
    scheduleSpy = vi.spyOn(apiClientModule, "scheduleProactiveRefresh").mockImplementation(() => {});
    cancelSpy = vi.spyOn(apiClientModule, "cancelProactiveRefresh").mockImplementation(() => {});
});

afterEach(() => {
    server.resetHandlers();
    scheduleSpy.mockRestore();
    cancelSpy.mockRestore();
    localStorage.clear();
    sessionStorage.clear();
});

afterAll(() => {
    server.close();
});

describe("AuthProvider", () => {
    describe("proactive refresh lifecycle", () => {
        test("calls scheduleProactiveRefresh after successful authentication", async () => {
            const exp = Math.floor((Date.now() + 3600000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(exp));
            localStorage.setItem("access_token", makeJwt(exp));

            server.use(
                http.get("http://localhost:3000/api/v1/users/me", () => {
                    return HttpResponse.json({
                        username: "test-user",
                        email: "test@example.com",
                    });
                })
            );

            render(
                <TestWrapper>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("true");
            });

            expect(scheduleSpy).toHaveBeenCalled();
        });

        test("does not call scheduleProactiveRefresh when auth check fails", async () => {
            server.use(
                http.get("http://localhost:3000/api/v1/users/me", () => {
                    return new HttpResponse(null, { status: 401 });
                })
            );

            render(
                <TestWrapper>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("false");
            });

            expect(scheduleSpy).not.toHaveBeenCalled();
        });

        test("calls cancelProactiveRefresh on logout", async () => {
            const exp = Math.floor((Date.now() + 3600000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(exp));
            localStorage.setItem("access_token", makeJwt(exp));

            server.use(
                http.get("http://localhost:3000/api/v1/users/me", () => {
                    return HttpResponse.json({
                        username: "test-user",
                        email: "test@example.com",
                    });
                }),
                http.post("http://localhost:3000/api/v1/auth/logout", () => {
                    return HttpResponse.json({ success: true });
                })
            );

            // Mock window.location.href
            const originalLocation = window.location;
            Object.defineProperty(window, "location", {
                value: { ...originalLocation, href: "" },
                writable: true,
                configurable: true,
            });

            render(
                <TestWrapper>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("true");
            });

            cancelSpy.mockClear();

            const user = userEvent.setup();
            await act(async () => {
                await user.click(screen.getByTestId("logout-btn"));
            });

            expect(cancelSpy).toHaveBeenCalled();
            expect(localStorage.getItem("access_token")).toBeNull();
            expect(localStorage.getItem("sam_access_token")).toBeNull();
            expect(localStorage.getItem("refresh_token")).toBeNull();

            Object.defineProperty(window, "location", {
                value: originalLocation,
                writable: true,
                configurable: true,
            });
        });

        test("evicts every cached query on logout so no prior-user data can leak", async () => {
            const exp = Math.floor((Date.now() + 3600000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(exp));
            localStorage.setItem("access_token", makeJwt(exp));

            server.use(
                http.get("http://localhost:3000/api/v1/users/me", () => {
                    return HttpResponse.json({
                        username: "test-user",
                        email: "test@example.com",
                    });
                }),
                http.post("http://localhost:3000/api/v1/auth/logout", () => {
                    return HttpResponse.json({ success: true });
                })
            );

            // Pre-populate the QueryClient with data from "user A". After logout,
            // none of these keys should remain in the cache.
            const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
            const recentKey = sessionKeys.recent("alice", 10);
            const sharedKey = shareKeys.sharedWithMe("alice");
            queryClient.setQueryData(recentKey, [{ id: "sess-A", name: "User A's chat" }]);
            queryClient.setQueryData(sharedKey, [{ shareId: "share-A" }]);
            queryClient.setQueryData(["unrelated", "key"], { foo: "bar" });

            const originalLocation = window.location;
            Object.defineProperty(window, "location", {
                value: { ...originalLocation, href: "" },
                writable: true,
                configurable: true,
            });

            render(
                <TestWrapper queryClient={queryClient}>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("true");
            });

            // Sanity check: the seeded cache entries are present before logout.
            expect(queryClient.getQueryData(recentKey)).toBeDefined();
            expect(queryClient.getQueryData(sharedKey)).toBeDefined();
            expect(queryClient.getQueryData(["unrelated", "key"])).toBeDefined();

            const user = userEvent.setup();
            await act(async () => {
                await user.click(screen.getByTestId("logout-btn"));
            });

            // Every query — user-scoped or otherwise — must be evicted.
            expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
            expect(queryClient.getQueryData(recentKey)).toBeUndefined();
            expect(queryClient.getQueryData(sharedKey)).toBeUndefined();
            expect(queryClient.getQueryData(["unrelated", "key"])).toBeUndefined();

            Object.defineProperty(window, "location", {
                value: originalLocation,
                writable: true,
                configurable: true,
            });
        });

        test("calls cancelProactiveRefresh on unmount", async () => {
            const exp = Math.floor((Date.now() + 3600000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(exp));

            server.use(
                http.get("http://localhost:3000/api/v1/users/me", () => {
                    return HttpResponse.json({
                        username: "test-user",
                        email: "test@example.com",
                    });
                })
            );

            const { unmount } = render(
                <TestWrapper>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("true");
            });

            cancelSpy.mockClear();
            unmount();

            expect(cancelSpy).toHaveBeenCalled();
        });
    });

    describe("no-auth mode", () => {
        test("does not call scheduleProactiveRefresh when authorization is disabled", async () => {
            render(
                <TestWrapper useAuthorization={false}>
                    <AuthConsumer />
                </TestWrapper>
            );

            await waitFor(() => {
                expect(screen.getByTestId("authenticated").textContent).toBe("true");
            });

            expect(scheduleSpy).not.toHaveBeenCalled();
        });
    });
});
