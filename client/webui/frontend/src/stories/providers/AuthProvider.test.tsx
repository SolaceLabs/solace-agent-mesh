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

import { MockConfigProvider } from "@/stories/mocks/MockConfigProvider";
import { CsrfContext, type CsrfContextValue } from "@/lib/contexts/CsrfContext";
import { AuthContext } from "@/lib/contexts/AuthContext";
import { AuthProvider } from "@/lib/providers/AuthProvider";
import * as apiClientModule from "@/lib/api/client";

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

// Wrapper with all required providers
function TestWrapper({ children, useAuthorization = true }: { children: React.ReactNode; useAuthorization?: boolean }) {
    return (
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
