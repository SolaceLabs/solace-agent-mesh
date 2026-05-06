/**
 * Integration tests for the user-scoping behaviour of useRecentSessions /
 * useInfiniteSessions. When the auth-context user changes, both hooks must
 * issue a fresh fetch under the new key rather than serving the prior user's
 * cached pages.
 */
import React from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthContext, type AuthContextValue } from "@/lib/contexts/AuthContext";
import { useRecentSessions, useInfiniteSessions } from "@/lib/api/sessions/hooks";
import * as sessionService from "@/lib/api/sessions/service";
import type { Session } from "@/lib/types";

function makeAuthValue(userInfo: Record<string, unknown> | null): AuthContextValue {
    return {
        isAuthenticated: true,
        useAuthorization: true,
        login: () => {},
        logout: () => {},
        userInfo,
    };
}

function makeSession(overrides: Partial<Session> = {}): Session {
    return {
        id: "sess-x",
        name: "Session",
        userId: "alice",
        createdTime: "2024-01-01T00:00:00Z",
        updatedTime: "2024-01-01T00:00:00Z",
        ...overrides,
    };
}

describe("useRecentSessions / useInfiniteSessions — auth user switch", () => {
    let queryClient: QueryClient;
    let recentSpy: ReturnType<typeof vi.spyOn>;
    let infiniteSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    });

    afterEach(() => {
        vi.restoreAllMocks();
        queryClient.clear();
    });

    function makeWrapper(authValue: { current: AuthContextValue }) {
        return function Wrapper({ children }: { children: React.ReactNode }) {
            return (
                <QueryClientProvider client={queryClient}>
                    <AuthContext.Provider value={authValue.current}>{children}</AuthContext.Provider>
                </QueryClientProvider>
            );
        };
    }

    test("useRecentSessions refetches under a new key when auth user switches", async () => {
        const authRef = { current: makeAuthValue({ username: "alice" }) };
        recentSpy = vi.spyOn(sessionService, "getRecentSessions").mockImplementation(async () => {
            // Resolve based on the *current* auth user — emulate the server.
            const u = authRef.current.userInfo?.username as string | undefined;
            if (u === "alice") return [makeSession({ id: "alice-sess", name: "Alice's chat", userId: "alice" })];
            if (u === "bob") return [makeSession({ id: "bob-sess", name: "Bob's chat", userId: "bob" })];
            return [];
        });

        const wrapper = makeWrapper(authRef);

        const { result, rerender } = renderHook(() => useRecentSessions(10), { wrapper });

        await waitFor(() => expect(result.current.data).toBeDefined());
        expect(result.current.data?.[0]?.id).toBe("alice-sess");
        expect(recentSpy).toHaveBeenCalledTimes(1);

        // Switch auth user — the query key changes, so a fresh fetch must occur
        // and the data returned must be Bob's, not Alice's cached page.
        authRef.current = makeAuthValue({ username: "bob" });
        rerender();

        await waitFor(() => expect(result.current.data?.[0]?.id).toBe("bob-sess"));
        expect(recentSpy).toHaveBeenCalledTimes(2);

        // Alice's cached entry must still be reachable under her own key —
        // proving the new fetch went to a *different* cache slot.
        const aliceCached = queryClient.getQueryData(["sessions", "list", "recent", "alice", 10]) as Session[] | undefined;
        const bobCached = queryClient.getQueryData(["sessions", "list", "recent", "bob", 10]) as Session[] | undefined;
        expect(aliceCached?.[0]?.id).toBe("alice-sess");
        expect(bobCached?.[0]?.id).toBe("bob-sess");
    });

    test("useInfiniteSessions refetches under a new key when auth user switches", async () => {
        const authRef = { current: makeAuthValue({ username: "alice" }) };
        infiniteSpy = vi.spyOn(sessionService, "getPaginatedSessions").mockImplementation(async () => {
            const u = authRef.current.userInfo?.username as string | undefined;
            const session = u === "bob" ? makeSession({ id: "bob-sess", userId: "bob" }) : makeSession({ id: "alice-sess", userId: "alice" });
            return {
                data: [session],
                meta: { pagination: { pageNumber: 1, count: 1, pageSize: 20, nextPage: null, totalPages: 1 } },
            };
        });

        const wrapper = makeWrapper(authRef);

        const { result, rerender } = renderHook(() => useInfiniteSessions(20), { wrapper });

        await waitFor(() => expect(result.current.data).toBeDefined());
        expect(result.current.data?.pages?.[0]?.data?.[0]?.id).toBe("alice-sess");
        expect(infiniteSpy).toHaveBeenCalledTimes(1);

        authRef.current = makeAuthValue({ username: "bob" });
        rerender();

        await waitFor(() => expect(result.current.data?.pages?.[0]?.data?.[0]?.id).toBe("bob-sess"));
        expect(infiniteSpy).toHaveBeenCalledTimes(2);
    });
});
