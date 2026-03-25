/**
 * Tests for useCollaborativeSession hook — collaborative session detection and state management.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, beforeEach, vi } from "vitest";

describe("useCollaborativeSession", () => {
    let useCollaborativeSession: typeof import("@/lib/hooks/useCollaborativeSession").useCollaborativeSession;
    let mockWebuiGet: ReturnType<typeof vi.fn>;
    let mockUserInfo: { username?: string };

    beforeEach(async () => {
        vi.resetModules();

        mockWebuiGet = vi.fn().mockResolvedValue({});
        mockUserInfo = { username: undefined };

        vi.doMock("@/lib/api", () => ({
            api: {
                webui: { get: mockWebuiGet },
            },
        }));

        vi.doMock("@/lib/hooks/useAuthContext", () => ({
            useAuthContext: () => ({
                userInfo: mockUserInfo,
            }),
        }));

        vi.doMock("@/lib/api/share", () => ({
            getShareLinkForSession: vi.fn().mockResolvedValue(null),
            getShareUsers: vi.fn().mockResolvedValue({ users: [] }),
        }));

        const mod = await import("@/lib/hooks/useCollaborativeSession");
        useCollaborativeSession = mod.useCollaborativeSession;
    });

    describe("initial state", () => {
        test("all collaborative flags are false and owner fields are null", () => {
            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            expect(result.current.isCollaborativeSession).toBe(false);
            expect(result.current.hasSharedEditors).toBe(false);
            expect(result.current.currentUserEmail).toBe("");
            expect(result.current.sessionOwnerName).toBeNull();
            expect(result.current.sessionOwnerEmail).toBeNull();
        });
    });

    describe("detectCollaborativeSession", () => {
        test("when current user IS the owner, session is not collaborative", async () => {
            mockUserInfo.username = "user-abc";

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            await act(async () => {
                await result.current.detectCollaborativeSession({ userId: "user-abc", ownerDisplayName: "Alice", ownerEmail: "alice@example.com" }, "session-1");
            });

            expect(result.current.isCollaborativeSession).toBe(false);
            expect(result.current.sessionOwnerName).toBeNull();
            expect(result.current.sessionOwnerEmail).toBeNull();
        });

        test("when current user is NOT the owner, session is collaborative", async () => {
            mockUserInfo.username = "user-abc";

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            await act(async () => {
                await result.current.detectCollaborativeSession({ userId: "user-xyz", ownerDisplayName: "Bob", ownerEmail: "bob@example.com" }, "session-1");
            });

            expect(result.current.isCollaborativeSession).toBe(true);
            expect(result.current.sessionOwnerName).toBe("Bob");
            expect(result.current.sessionOwnerEmail).toBe("bob@example.com");
        });

        test("when owner has no display name, falls back to userId", async () => {
            mockUserInfo.username = "user-abc";

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            await act(async () => {
                await result.current.detectCollaborativeSession({ userId: "user-xyz", ownerDisplayName: null, ownerEmail: null }, "session-1");
            });

            expect(result.current.isCollaborativeSession).toBe(true);
            expect(result.current.sessionOwnerName).toBe("user-xyz");
            expect(result.current.sessionOwnerEmail).toBe("user-xyz");
        });
    });

    describe("resetCollaborativeState", () => {
        test("resets all collaborative fields to defaults", async () => {
            mockUserInfo.username = "user-abc";

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            // First, put the hook into a collaborative state
            await act(async () => {
                await result.current.detectCollaborativeSession({ userId: "user-xyz", ownerDisplayName: "Bob", ownerEmail: "bob@example.com" }, "session-1");
            });

            expect(result.current.isCollaborativeSession).toBe(true);

            // Now reset
            act(() => {
                result.current.resetCollaborativeState();
            });

            expect(result.current.isCollaborativeSession).toBe(false);
            expect(result.current.hasSharedEditors).toBe(false);
            expect(result.current.sessionOwnerName).toBeNull();
            expect(result.current.sessionOwnerEmail).toBeNull();
        });
    });

    describe("getCurrentUserId", () => {
        test("returns userInfo.username when available", () => {
            mockUserInfo.username = "user-abc";

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            expect(result.current.getCurrentUserId()).toBe("user-abc");
        });

        test("returns null when userInfo.username is not available and no auth fallback", () => {
            mockUserInfo.username = undefined;
            mockWebuiGet.mockResolvedValue({});

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            expect(result.current.getCurrentUserId()).toBeNull();
        });

        test("falls back to auth/me id when userInfo.username is not set", async () => {
            mockUserInfo.username = undefined;
            mockWebuiGet.mockResolvedValue({ id: "auth-user-id", email: "auth@example.com" });

            const { result } = renderHook(() => useCollaborativeSession("session-1"));

            // Wait for the useEffect that calls /auth/me to complete
            await act(async () => {
                await vi.waitFor(() => {
                    expect(mockWebuiGet).toHaveBeenCalledWith("/api/v1/auth/me");
                });
            });

            expect(result.current.getCurrentUserId()).toBe("auth-user-id");
        });
    });
});
