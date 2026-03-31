/**
 * Tests for useSseErrorRecovery hook — SSE error recovery with token refresh.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import * as apiClientModule from "@/lib/api/client";
import { useSseErrorRecovery } from "@/lib/hooks/useSseErrorRecovery";
import type { SseErrorRecoveryCallbacks, SseErrorRecoveryState } from "@/lib/hooks/useSseErrorRecovery";

function createMockCallbacks(): SseErrorRecoveryCallbacks {
    return {
        closeCurrentEventSource: vi.fn(),
        setError: vi.fn(),
        setIsResponding: vi.fn(),
        setCurrentTaskId: vi.fn(),
        cleanupMessages: vi.fn(),
    };
}

function createMockState(overrides: Partial<SseErrorRecoveryState> = {}): SseErrorRecoveryState {
    return {
        isResponding: true,
        isFinalizing: { current: false },
        isCancelling: { current: false },
        currentTaskId: "task-123",
        ...overrides,
    };
}

let refreshTokenSpy: ReturnType<typeof vi.spyOn>;

describe("useSseErrorRecovery", () => {
    beforeEach(() => {
        refreshTokenSpy = vi.spyOn(apiClientModule, "refreshToken");
    });

    afterEach(() => {
        refreshTokenSpy.mockRestore();
        vi.restoreAllMocks();
    });

    describe("initial state", () => {
        test("returns sseReconnectKey starting at 0", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState();

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            expect(result.current.sseReconnectKey).toBe(0);
        });

        test("returns handleSseError function", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState();

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            expect(typeof result.current.handleSseError).toBe("function");
        });

        test("returns cleanupSseFailure function", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState();

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            expect(typeof result.current.cleanupSseFailure).toBe("function");
        });
    });

    describe("cleanupSseFailure", () => {
        test("calls setError, setIsResponding, setCurrentTaskId, and cleanupMessages", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState();

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.cleanupSseFailure("Test Title", "Test message");
            });

            expect(callbacks.setError).toHaveBeenCalledWith({ title: "Test Title", error: "Test message" });
            expect(callbacks.setIsResponding).toHaveBeenCalledWith(false);
            expect(callbacks.setCurrentTaskId).toHaveBeenCalledWith(null);
            expect(callbacks.cleanupMessages).toHaveBeenCalled();
        });
    });

    describe("handleSseError — token refresh path", () => {
        test("attempts token refresh on first SSE error when responding", async () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: "task-123" });
            refreshTokenSpy.mockResolvedValue("new-token");

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            // Should close the current event source
            expect(callbacks.closeCurrentEventSource).toHaveBeenCalled();
            // Should call refreshToken
            expect(refreshTokenSpy).toHaveBeenCalled();

            // Wait for the async .then() chain to flush and update state
            await act(async () => {
                await new Promise(resolve => setTimeout(resolve, 0));
            });

            // After successful refresh, sseReconnectKey should be bumped
            expect(result.current.sseReconnectKey).toBe(1);
        });

        test("calls cleanupSseFailure when refresh returns null", async () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: "task-456" });
            refreshTokenSpy.mockResolvedValue(null);

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            await act(async () => {
                await new Promise(resolve => setTimeout(resolve, 0));
            });

            expect(callbacks.setError).toHaveBeenCalledWith({
                title: "Connection Failed",
                error: "Session expired. Please log in again.",
            });
            expect(callbacks.setIsResponding).toHaveBeenCalledWith(false);
            expect(callbacks.setCurrentTaskId).toHaveBeenCalledWith(null);
        });

        test("calls cleanupSseFailure when refresh throws", async () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: "task-789" });
            refreshTokenSpy.mockRejectedValue(new Error("Network error"));

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            await act(async () => {
                await new Promise(resolve => setTimeout(resolve, 0));
            });

            expect(callbacks.setError).toHaveBeenCalledWith({
                title: "Connection Failed",
                error: "Connection lost. Please try again.",
            });
            expect(callbacks.setIsResponding).toHaveBeenCalledWith(false);
            expect(callbacks.setCurrentTaskId).toHaveBeenCalledWith(null);
        });

        test("does not attempt refresh on second SSE error (retry-once guard)", async () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: "task-123" });
            refreshTokenSpy.mockResolvedValue("new-token");

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            // First error — triggers refresh
            act(() => {
                result.current.handleSseError();
            });

            await act(async () => {
                await new Promise(resolve => setTimeout(resolve, 0));
            });

            expect(result.current.sseReconnectKey).toBe(1);

            refreshTokenSpy.mockClear();
            (callbacks.closeCurrentEventSource as ReturnType<typeof vi.fn>).mockClear();

            // Second error — should NOT trigger refresh (retry-once guard)
            act(() => {
                result.current.handleSseError();
            });

            // refreshToken should NOT be called again
            expect(refreshTokenSpy).not.toHaveBeenCalled();
            // But the normal error handling should still run
            expect(callbacks.setError).toHaveBeenCalledWith({
                title: "Connection Failed",
                error: "Connection lost. Please try again.",
            });
        });
    });

    describe("handleSseError — non-refresh path", () => {
        test("does not attempt refresh when not responding", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: false, currentTaskId: "task-123" });

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            expect(refreshTokenSpy).not.toHaveBeenCalled();
            expect(callbacks.cleanupMessages).toHaveBeenCalled();
        });

        test("does not attempt refresh when isFinalizing", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({
                isResponding: true,
                currentTaskId: "task-123",
                isFinalizing: { current: true },
            });

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            expect(refreshTokenSpy).not.toHaveBeenCalled();
            expect(callbacks.setError).not.toHaveBeenCalled();
            expect(callbacks.cleanupMessages).toHaveBeenCalled();
        });

        test("does not attempt refresh when isCancelling", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({
                isResponding: true,
                currentTaskId: "task-123",
                isCancelling: { current: true },
            });

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            expect(refreshTokenSpy).not.toHaveBeenCalled();
            expect(callbacks.setError).not.toHaveBeenCalled();
        });

        test("does not attempt refresh when no currentTaskId", () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: null });

            const { result } = renderHook(() => useSseErrorRecovery(state, callbacks));

            act(() => {
                result.current.handleSseError();
            });

            expect(refreshTokenSpy).not.toHaveBeenCalled();
        });
    });

    describe("task ID change resets refresh guard", () => {
        test("resets sseRefreshAttempted when task ID changes", async () => {
            const callbacks = createMockCallbacks();
            const state = createMockState({ isResponding: true, currentTaskId: "task-A" });
            refreshTokenSpy.mockResolvedValue("new-token");

            const { result, rerender } = renderHook(({ taskId }) => useSseErrorRecovery({ ...state, currentTaskId: taskId }, callbacks), { initialProps: { taskId: "task-A" } });

            // First error on task-A — triggers refresh
            act(() => {
                result.current.handleSseError();
            });

            await act(async () => {
                await new Promise(resolve => setTimeout(resolve, 0));
            });

            expect(result.current.sseReconnectKey).toBe(1);

            refreshTokenSpy.mockClear();

            // Change to a new task
            rerender({ taskId: "task-B" });

            // Error on task-B — should trigger refresh again (guard was reset)
            act(() => {
                result.current.handleSseError();
            });

            expect(refreshTokenSpy).toHaveBeenCalled();
        });
    });
});
