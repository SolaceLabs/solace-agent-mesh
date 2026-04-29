/**
 * Tests for useCacheUserId — the source of the user-scoped portion of every
 * cache key. If this hook returns the wrong value, cache keys collapse and
 * users could see another user's cached data.
 */
import React from "react";
import { renderHook } from "@testing-library/react";
import { describe, test, expect } from "vitest";

import { AuthContext, type AuthContextValue } from "@/lib/contexts/AuthContext";
import { useCacheUserId } from "@/lib/hooks/useCacheUserId";

function wrapperWithUserInfo(userInfo: Record<string, unknown> | null) {
    const value: AuthContextValue = {
        isAuthenticated: true,
        useAuthorization: true,
        login: () => {},
        logout: () => {},
        userInfo,
    };
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
    };
}

describe("useCacheUserId", () => {
    test("returns username when present", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ username: "alice", id: "alice-id" }),
        });
        expect(result.current).toBe("alice");
    });

    test("falls back to id when username is missing", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ id: "user-42" }),
        });
        expect(result.current).toBe("user-42");
    });

    test("returns 'anonymous' when userInfo is null", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo(null),
        });
        expect(result.current).toBe("anonymous");
    });

    test("returns 'anonymous' when both username and id are missing", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ email: "x@y.z" }),
        });
        expect(result.current).toBe("anonymous");
    });

    test("non-string username falls through to id", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ username: 12345, id: "fallback-id" }),
        });
        expect(result.current).toBe("fallback-id");
    });

    test("empty-string username falls through to id", () => {
        const { result } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ username: "", id: "fallback-id" }),
        });
        expect(result.current).toBe("fallback-id");
    });

    test("different users get different cache identifiers", () => {
        const { result: a } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ username: "alice" }),
        });
        const { result: b } = renderHook(() => useCacheUserId(), {
            wrapper: wrapperWithUserInfo({ username: "bob" }),
        });
        expect(a.current).not.toBe(b.current);
    });
});
