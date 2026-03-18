/**
 * Tests for proactive token refresh, token lifecycle, and related utilities
 * in client.ts.
 */
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { refreshToken, scheduleProactiveRefresh, cancelProactiveRefresh, api } from "@/lib/api/client";

// Helper: create a minimal JWT with a given exp (seconds since epoch)
function makeJwt(exp: number): string {
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({ exp, sub: "test-user" }));
    return `${header}.${payload}.fake-signature`;
}

// Helper: create a JWT using base64url encoding (with - and _ chars)
function makeBase64UrlJwt(exp: number): string {
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
    const payload = btoa(JSON.stringify({ exp, sub: "test+user/special" }))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");
    return `${header}.${payload}.fake-signature`;
}

describe("Proactive Token Refresh", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        localStorage.clear();
        sessionStorage.clear();
        cancelProactiveRefresh();
    });

    afterEach(() => {
        cancelProactiveRefresh();
        vi.useRealTimers();
        vi.restoreAllMocks();
        localStorage.clear();
        sessionStorage.clear();
    });

    describe("scheduleProactiveRefresh", () => {
        test("does nothing when no tokens are in localStorage", () => {
            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();
            // Should not schedule any timer (only the internal clearTimeout call)
            const relevantCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(relevantCalls.length).toBe(0);
        });

        test("schedules refresh ~5 minutes before token expiry", () => {
            const now = Date.now();
            const expInSeconds = Math.floor((now + 60 * 60 * 1000) / 1000); // 1 hour from now
            const token = makeJwt(expInSeconds);
            localStorage.setItem("sam_access_token", token);

            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();

            // Should schedule a timer. The delay should be ~55 minutes (60min - 5min margin)
            const timerCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(timerCalls.length).toBeGreaterThanOrEqual(1);

            // The delay should be approximately 55 minutes (3300000ms), give or take a few ms
            const lastCall = timerCalls[timerCalls.length - 1];
            const delay = lastCall[1] as number;
            expect(delay).toBeGreaterThan(50 * 60 * 1000); // > 50 min
            expect(delay).toBeLessThan(56 * 60 * 1000); // < 56 min
        });

        test("uses minimum delay floor for near-expiry tokens", () => {
            const now = Date.now();
            // Token expires in 2 minutes — within the 5-minute margin
            const expInSeconds = Math.floor((now + 2 * 60 * 1000) / 1000);
            const token = makeJwt(expInSeconds);
            localStorage.setItem("sam_access_token", token);

            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();

            // Should schedule with the minimum floor delay (30 seconds)
            const timerCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(timerCalls.length).toBeGreaterThanOrEqual(1);
            const lastCall = timerCalls[timerCalls.length - 1];
            const delay = lastCall[1] as number;
            expect(delay).toBe(30 * 1000); // MIN_PROACTIVE_REFRESH_DELAY_MS
        });

        test("uses minimum delay floor for already-expired tokens", () => {
            const now = Date.now();
            // Token already expired 10 minutes ago
            const expInSeconds = Math.floor((now - 10 * 60 * 1000) / 1000);
            const token = makeJwt(expInSeconds);
            localStorage.setItem("access_token", token);

            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();

            const timerCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(timerCalls.length).toBeGreaterThanOrEqual(1);
            const lastCall = timerCalls[timerCalls.length - 1];
            const delay = lastCall[1] as number;
            expect(delay).toBe(30 * 1000); // MIN_PROACTIVE_REFRESH_DELAY_MS
        });

        test("picks the earliest expiring token when both are present", () => {
            const now = Date.now();
            // sam_access_token expires in 30 min
            const samExp = Math.floor((now + 30 * 60 * 1000) / 1000);
            // access_token expires in 60 min
            const accessExp = Math.floor((now + 60 * 60 * 1000) / 1000);

            localStorage.setItem("sam_access_token", makeJwt(samExp));
            localStorage.setItem("access_token", makeJwt(accessExp));

            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();

            // Should use the sam_access_token expiry (30min - 5min margin = 25min)
            const timerCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(timerCalls.length).toBeGreaterThanOrEqual(1);
            const lastCall = timerCalls[timerCalls.length - 1];
            const delay = lastCall[1] as number;
            expect(delay).toBeGreaterThan(20 * 60 * 1000); // > 20 min
            expect(delay).toBeLessThan(26 * 60 * 1000); // < 26 min
        });

        test("handles base64url-encoded JWT tokens", () => {
            const now = Date.now();
            const expInSeconds = Math.floor((now + 60 * 60 * 1000) / 1000);
            const token = makeBase64UrlJwt(expInSeconds);
            localStorage.setItem("sam_access_token", token);

            const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
            scheduleProactiveRefresh();

            // Should successfully decode and schedule
            const timerCalls = setTimeoutSpy.mock.calls.filter(([fn]) => typeof fn === "function");
            expect(timerCalls.length).toBeGreaterThanOrEqual(1);
        });

        test("handles non-JWT tokens gracefully", () => {
            localStorage.setItem("access_token", "not-a-jwt-token");

            // Should not throw
            expect(() => scheduleProactiveRefresh()).not.toThrow();
        });

        test("handles malformed JWT payload gracefully", () => {
            localStorage.setItem("access_token", "header.!!!invalid-base64!!!.signature");

            expect(() => scheduleProactiveRefresh()).not.toThrow();
        });

        test("clears previous timer when called again", () => {
            const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
            const now = Date.now();
            const expInSeconds = Math.floor((now + 60 * 60 * 1000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(expInSeconds));

            scheduleProactiveRefresh();
            scheduleProactiveRefresh(); // Second call should clear the first timer

            // clearTimeout should have been called at least once for the re-schedule
            expect(clearTimeoutSpy).toHaveBeenCalled();
        });
    });

    describe("cancelProactiveRefresh", () => {
        test("cancels a scheduled timer", () => {
            const now = Date.now();
            const expInSeconds = Math.floor((now + 60 * 60 * 1000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(expInSeconds));

            scheduleProactiveRefresh();
            const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
            cancelProactiveRefresh();

            expect(clearTimeoutSpy).toHaveBeenCalled();
        });

        test("is safe to call when no timer is scheduled", () => {
            expect(() => cancelProactiveRefresh()).not.toThrow();
        });

        test("is idempotent", () => {
            const now = Date.now();
            const expInSeconds = Math.floor((now + 60 * 60 * 1000) / 1000);
            localStorage.setItem("sam_access_token", makeJwt(expInSeconds));

            scheduleProactiveRefresh();
            cancelProactiveRefresh();
            cancelProactiveRefresh(); // Second call should be safe

            expect(true).toBe(true); // No error thrown
        });
    });

    describe("refreshToken", () => {
        test("returns null when logout_in_progress is set", async () => {
            sessionStorage.setItem("logout_in_progress", "true");
            localStorage.setItem("refresh_token", "some-token");

            const result = await refreshToken();
            expect(result).toBeNull();
        });

        test("returns null when no refresh_token exists", async () => {
            const result = await refreshToken();
            expect(result).toBeNull();
        });

        test("deduplicates concurrent refresh calls", async () => {
            localStorage.setItem("refresh_token", "test-refresh-token");

            const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
                new Response(
                    JSON.stringify({
                        access_token: "new-access",
                        sam_access_token: "",
                        refresh_token: "new-refresh",
                    }),
                    { status: 200 }
                )
            );

            // Fire two concurrent refreshes
            const [result1, result2] = await Promise.all([refreshToken(), refreshToken()]);

            // Both should resolve, but fetch should only be called once
            expect(fetchSpy).toHaveBeenCalledTimes(1);
            expect(result1).toBe(result2);
        });

        test("clears tokens and redirects on refresh failure", async () => {
            localStorage.setItem("refresh_token", "test-refresh-token");
            localStorage.setItem("access_token", "old-access");

            vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("Unauthorized", { status: 401 }));

            // Mock location.href setter
            const locationSpy = vi.spyOn(globalThis, "location", "get").mockReturnValue({
                ...globalThis.location,
                href: "",
            } as Location);

            Object.defineProperty(globalThis, "location", {
                value: { href: "" },
                writable: true,
                configurable: true,
            });

            await refreshToken();

            // Tokens should be cleared
            expect(localStorage.getItem("access_token")).toBeNull();
            expect(localStorage.getItem("refresh_token")).toBeNull();

            // Restore location
            locationSpy?.mockRestore();
        });
    });
});

describe("authenticatedFetch — no-token path (401 storm prevention)", () => {
    beforeEach(() => {
        localStorage.clear();
        sessionStorage.clear();
        cancelProactiveRefresh();
        // Configure api with a base URL so requests resolve to a known path
        api.configure("", "");
        Object.defineProperty(globalThis, "location", {
            value: { href: "" },
            writable: true,
            configurable: true,
        });
    });

    afterEach(() => {
        cancelProactiveRefresh();
        vi.restoreAllMocks();
        localStorage.clear();
        sessionStorage.clear();
    });

    test("attempts token refresh when no bearer token is in localStorage", async () => {
        // No access_token in localStorage
        localStorage.setItem("refresh_token", "valid-refresh-token");

        const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
            new Response(
                JSON.stringify({
                    access_token: "new-access-token",
                    sam_access_token: "",
                    refresh_token: "new-refresh-token",
                }),
                { status: 200 }
            )
        );

        // Trigger a request via the api client — it will call authenticatedFetch internally
        await api.webui.get("/api/v1/users/me").catch(() => {
            /* ignore response errors */
        });

        // fetch should have been called twice: once for /auth/refresh, once for the actual request
        const calls = fetchSpy.mock.calls.map(([url]) => url as string);
        expect(calls.some(url => url.includes("/auth/refresh"))).toBe(true);
        expect(calls.some(url => url.includes("/users/me"))).toBe(true);
    });

    test("returns synthetic 401 when no bearer token and no refresh token", async () => {
        // No tokens at all in localStorage — refreshToken() returns null immediately
        // (no refresh_token present), so authenticatedFetch returns a synthetic 401
        // without navigating. The redirect to login is handled by refreshToken() only
        // when a refresh_token exists but the server rejects it.
        const fetchSpy = vi.spyOn(globalThis, "fetch");

        let caughtError: Error | null = null;
        try {
            await api.webui.get("/api/v1/users/me");
        } catch (e) {
            caughtError = e as Error;
        }

        // Should NOT have called fetch for the actual endpoint (short-circuited)
        const apiCalls = fetchSpy.mock.calls.filter(([url]) => (url as string).includes("/users/me"));
        expect(apiCalls).toHaveLength(0);

        // Should have thrown "Not authenticated" (from fetchJsonWithError → fetchWithError)
        expect(caughtError).not.toBeNull();
        expect(caughtError?.message).toContain("Not authenticated");
    });

    test("deduplicates concurrent no-token requests into a single refresh call", async () => {
        // No access_token, but refresh_token present
        localStorage.setItem("refresh_token", "valid-refresh-token");

        let refreshCallCount = 0;
        const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async url => {
            if ((url as string).includes("/auth/refresh")) {
                refreshCallCount++;
                return new Response(
                    JSON.stringify({
                        access_token: "new-access-token",
                        sam_access_token: "",
                        refresh_token: "new-refresh-token",
                    }),
                    { status: 200 }
                );
            }
            return new Response(JSON.stringify({ id: "user-1" }), { status: 200 });
        });

        // Fire 5 concurrent requests simultaneously — all with no token
        await Promise.all([
            api.webui.get("/api/v1/users/me").catch(() => {}),
            api.webui.get("/api/v1/users/me").catch(() => {}),
            api.webui.get("/api/v1/users/me").catch(() => {}),
            api.webui.get("/api/v1/users/me").catch(() => {}),
            api.webui.get("/api/v1/users/me").catch(() => {}),
        ]);

        // The refresh endpoint should only be called ONCE despite 5 concurrent requests
        expect(refreshCallCount).toBe(1);

        fetchSpy.mockRestore();
    });
});
