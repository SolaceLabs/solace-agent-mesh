/**
 * Tests for useTurnDividerAnimation — animationReducer logic and hook state transitions.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

import { animationReducer, useTurnDividerAnimation } from "@/lib/hooks/useTurnDividerAnimation";
import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

// ---------------------------------------------------------------------------
// animationReducer — pure function unit tests
// ---------------------------------------------------------------------------

const INITIAL = {
    isHistoryRevealed: false,
    isExitingHistory: false,
    isWaitingToExit: false,
};

describe("animationReducer", () => {
    test("DIVIDER_CHANGED resets revealed and starts exit animation", () => {
        const state = { isHistoryRevealed: true, isExitingHistory: false, isWaitingToExit: false };
        const next = animationReducer(state, { type: "DIVIDER_CHANGED" });
        expect(next).toEqual({ isHistoryRevealed: false, isExitingHistory: true, isWaitingToExit: false });
    });

    test("DIVIDER_REMOVED clears revealed but preserves isExitingHistory", () => {
        const exitingState = { isHistoryRevealed: true, isExitingHistory: true, isWaitingToExit: false };
        const next = animationReducer(exitingState, { type: "DIVIDER_REMOVED" });
        expect(next).toEqual({ isHistoryRevealed: false, isExitingHistory: true, isWaitingToExit: false });

        const idleState = { isHistoryRevealed: true, isExitingHistory: false, isWaitingToExit: false };
        const next2 = animationReducer(idleState, { type: "DIVIDER_REMOVED" });
        expect(next2).toEqual({ isHistoryRevealed: false, isExitingHistory: false, isWaitingToExit: false });
    });

    test("SESSION_CHANGED resets both flags", () => {
        const state = { isHistoryRevealed: true, isExitingHistory: true, isWaitingToExit: false };
        const next = animationReducer(state, { type: "SESSION_CHANGED" });
        expect(next).toEqual({ isHistoryRevealed: false, isExitingHistory: false, isWaitingToExit: false });
    });

    test("REVEAL_HISTORY sets isHistoryRevealed without affecting exit state", () => {
        const next = animationReducer(INITIAL, { type: "REVEAL_HISTORY" });
        expect(next).toEqual({ isHistoryRevealed: true, isExitingHistory: false, isWaitingToExit: false });

        const exitingState = { isHistoryRevealed: false, isExitingHistory: true, isWaitingToExit: false };
        const next2 = animationReducer(exitingState, { type: "REVEAL_HISTORY" });
        expect(next2).toEqual({ isHistoryRevealed: true, isExitingHistory: true, isWaitingToExit: false });
    });

    test("EXIT_COMPLETE clears isExitingHistory without affecting reveal", () => {
        const state = { isHistoryRevealed: false, isExitingHistory: true, isWaitingToExit: false };
        const next = animationReducer(state, { type: "EXIT_COMPLETE" });
        expect(next).toEqual({ isHistoryRevealed: false, isExitingHistory: false, isWaitingToExit: false });

        const revealedState = { isHistoryRevealed: true, isExitingHistory: true, isWaitingToExit: false };
        const next2 = animationReducer(revealedState, { type: "EXIT_COMPLETE" });
        expect(next2).toEqual({ isHistoryRevealed: true, isExitingHistory: false, isWaitingToExit: false });
    });

    test("unknown action returns state unchanged", () => {
        const state = { isHistoryRevealed: true, isExitingHistory: true, isWaitingToExit: false };
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const next = animationReducer(state, { type: "UNKNOWN" } as any);
        expect(next).toBe(state);
    });

    test("full lifecycle: reveal → collapse (new divider) → exit complete", () => {
        let state = INITIAL;

        // User scrolls up → reveal history
        state = animationReducer(state, { type: "REVEAL_HISTORY" });
        expect(state.isHistoryRevealed).toBe(true);
        expect(state.isExitingHistory).toBe(false);

        // New message submitted → divider changes, triggering exit animation
        state = animationReducer(state, { type: "DIVIDER_CHANGED" });
        expect(state.isHistoryRevealed).toBe(false);
        expect(state.isExitingHistory).toBe(true);

        // Exit animation finishes
        state = animationReducer(state, { type: "EXIT_COMPLETE" });
        expect(state.isHistoryRevealed).toBe(false);
        expect(state.isExitingHistory).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// useTurnDividerAnimation — renderHook-based tests
// ---------------------------------------------------------------------------

function createMockChatMessageListRef(scrollContainer?: HTMLElement) {
    return {
        current: {
            scrollContainer: scrollContainer ?? null,
            pauseAutoScroll: vi.fn().mockResolvedValue(undefined),
            scrollToBottom: vi.fn(),
        } as unknown as ChatMessageListRef,
    };
}

let rafCallbacks: Array<() => void> = [];
const originalRaf = globalThis.requestAnimationFrame;

beforeEach(() => {
    vi.useFakeTimers();
    rafCallbacks = [];
    globalThis.requestAnimationFrame = vi.fn((cb: FrameRequestCallback) => {
        rafCallbacks.push(() => cb(performance.now()));
        return rafCallbacks.length;
    }) as unknown as typeof requestAnimationFrame;
});

afterEach(() => {
    vi.useRealTimers();
    globalThis.requestAnimationFrame = originalRaf;
});

function flushRaf() {
    let safety = 10;
    while (rafCallbacks.length > 0 && safety-- > 0) {
        const batch = [...rafCallbacks];
        rafCallbacks = [];
        batch.forEach(cb => cb());
    }
}

describe("useTurnDividerAnimation — hook", () => {
    test("wheel scroll up at top reveals history when collapsed", () => {
        const container = document.createElement("div");
        Object.defineProperty(container, "scrollTop", { value: 0, writable: true });
        Object.defineProperty(container, "scrollHeight", { value: 500, writable: true });
        const chatMessageListRef = createMockChatMessageListRef(container);

        const { result } = renderHook(props => useTurnDividerAnimation(props), {
            initialProps: {
                turnDividerIndex: 2,
                messagesLength: 5,
                sessionId: "s1",
                chatMessageListRef,
            },
        });

        // Initially waiting — messages shown at bottom before exit starts
        expect(result.current.hasDivider).toBe(true);
        expect(result.current.isHistoryCollapsed).toBe(false);

        // Advance past the exit animation fallback timeout
        // Step 1: advance past the 600ms waiting delay → triggers DIVIDER_CHANGED
        act(() => {
            vi.advanceTimersByTime(700);
        });
        // Step 2: advance past the exit animation fallback timeout (SLIDE_OUT_DURATION_MS + 100)
        act(() => {
            vi.advanceTimersByTime(500);
        });
        // Flush rAFs from onExitComplete (pauseAutoScroll + scrollIntoView)
        act(() => flushRaf());
        act(() => flushRaf());

        // Now collapsed
        expect(result.current.isHistoryCollapsed).toBe(true);

        // Simulate wheel scroll up
        act(() => {
            container.dispatchEvent(new WheelEvent("wheel", { deltaY: -10 }));
        });

        expect(result.current.isHistoryRevealed).toBe(true);
        expect(result.current.isHistoryCollapsed).toBe(false);
    });

    test("touch swipe down at top reveals history when collapsed", () => {
        const container = document.createElement("div");
        Object.defineProperty(container, "scrollTop", { value: 0, writable: true });
        Object.defineProperty(container, "scrollHeight", { value: 500, writable: true });
        const chatMessageListRef = createMockChatMessageListRef(container);

        const { result } = renderHook(props => useTurnDividerAnimation(props), {
            initialProps: {
                turnDividerIndex: 2,
                messagesLength: 5,
                sessionId: "s1",
                chatMessageListRef,
            },
        });

        // Advance past exit animation
        // Step 1: advance past the 600ms waiting delay → triggers DIVIDER_CHANGED
        act(() => {
            vi.advanceTimersByTime(700);
        });
        // Step 2: advance past the exit animation fallback timeout (SLIDE_OUT_DURATION_MS + 100)
        act(() => {
            vi.advanceTimersByTime(500);
        });
        // Flush rAFs from onExitComplete (pauseAutoScroll + scrollIntoView)
        act(() => flushRaf());
        act(() => flushRaf());

        expect(result.current.isHistoryCollapsed).toBe(true);

        // Simulate touch swipe down (finger moves from y=100 to y=150)
        act(() => {
            container.dispatchEvent(new TouchEvent("touchstart", { touches: [{ clientY: 100 } as Touch] }));
            container.dispatchEvent(new TouchEvent("touchmove", { touches: [{ clientY: 150 } as Touch] }));
        });

        expect(result.current.isHistoryRevealed).toBe(true);
    });

    test("PageUp key at top reveals history when collapsed", () => {
        const container = document.createElement("div");
        Object.defineProperty(container, "scrollTop", { value: 0, writable: true });
        Object.defineProperty(container, "scrollHeight", { value: 500, writable: true });
        const chatMessageListRef = createMockChatMessageListRef(container);

        const { result } = renderHook(props => useTurnDividerAnimation(props), {
            initialProps: {
                turnDividerIndex: 2,
                messagesLength: 5,
                sessionId: "s1",
                chatMessageListRef,
            },
        });

        // Advance past exit animation
        // Step 1: advance past the 600ms waiting delay → triggers DIVIDER_CHANGED
        act(() => {
            vi.advanceTimersByTime(700);
        });
        // Step 2: advance past the exit animation fallback timeout (SLIDE_OUT_DURATION_MS + 100)
        act(() => {
            vi.advanceTimersByTime(500);
        });
        // Flush rAFs from onExitComplete (pauseAutoScroll + scrollIntoView)
        act(() => flushRaf());
        act(() => flushRaf());

        expect(result.current.isHistoryCollapsed).toBe(true);

        act(() => {
            container.dispatchEvent(new KeyboardEvent("keydown", { key: "PageUp" }));
        });

        expect(result.current.isHistoryRevealed).toBe(true);
    });

    test("exit animation lifecycle — timeout fallback fires EXIT_COMPLETE", () => {
        const chatMessageListRef = createMockChatMessageListRef();

        const { result, rerender } = renderHook(props => useTurnDividerAnimation(props), {
            initialProps: {
                turnDividerIndex: 2 as number | null,
                messagesLength: 5,
                sessionId: "s1",
                chatMessageListRef,
            },
        });

        // Change divider to trigger waiting → then DIVIDER_CHANGED after delay
        rerender({
            turnDividerIndex: 3,
            messagesLength: 6,
            sessionId: "s1",
            chatMessageListRef,
        });

        // Initially waiting, not yet exiting
        expect(result.current.isExitingHistory).toBe(false);

        // Advance past waiting delay → triggers DIVIDER_CHANGED
        act(() => {
            vi.advanceTimersByTime(700);
        });
        expect(result.current.isExitingHistory).toBe(true);

        // Advance past the exit animation fallback timeout (SLIDE_OUT_DURATION_MS + 100)
        act(() => {
            vi.advanceTimersByTime(500);
        });
        // Flush rAFs from onExitComplete (pauseAutoScroll + scrollIntoView)
        act(() => flushRaf());
        act(() => flushRaf());

        expect(result.current.isExitingHistory).toBe(false);
    });

    test("cleanup removes event listeners on unmount", () => {
        const container = document.createElement("div");
        Object.defineProperty(container, "scrollTop", { value: 0, writable: true });
        const removeEventListenerSpy = vi.spyOn(container, "removeEventListener");
        const chatMessageListRef = createMockChatMessageListRef(container);

        const { unmount } = renderHook(props => useTurnDividerAnimation(props), {
            initialProps: {
                turnDividerIndex: 2,
                messagesLength: 5,
                sessionId: "s1",
                chatMessageListRef,
            },
        });

        unmount();

        // Should have removed wheel, touchstart, touchmove, keydown listeners
        const removedEvents = removeEventListenerSpy.mock.calls.map(c => c[0]);
        expect(removedEvents).toContain("wheel");
        expect(removedEvents).toContain("touchstart");
        expect(removedEvents).toContain("touchmove");
        expect(removedEvents).toContain("keydown");
    });
});
