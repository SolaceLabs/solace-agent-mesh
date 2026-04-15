/**
 * Tests for useAutoScroll — pauseAutoScroll behavior, auto-scroll gating, and cleanup.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";

import { useAutoScroll } from "@/lib/components/ui/chat/hooks/useAutoScroll";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMockScrollElement(): HTMLDivElement {
    const el = document.createElement("div");
    Object.defineProperty(el, "scrollHeight", { value: 100, writable: true, configurable: true });
    Object.defineProperty(el, "clientHeight", { value: 100, writable: true, configurable: true });
    Object.defineProperty(el, "scrollTop", { value: 0, writable: true, configurable: true });
    el.scrollTo = vi.fn();
    return el;
}

function assignScrollRef(result: { current: ReturnType<typeof useAutoScroll> }) {
    const el = createMockScrollElement();
    (result.current.scrollRef as React.MutableRefObject<HTMLDivElement>).current = el;
    return el;
}

// Mock requestAnimationFrame to fire synchronously for deterministic tests
let rafCallbacks: Array<() => void> = [];
const originalRaf = globalThis.requestAnimationFrame;

beforeEach(() => {
    rafCallbacks = [];
    globalThis.requestAnimationFrame = vi.fn((cb: FrameRequestCallback) => {
        rafCallbacks.push(() => cb(performance.now()));
        return rafCallbacks.length;
    }) as unknown as typeof requestAnimationFrame;
});

afterEach(() => {
    globalThis.requestAnimationFrame = originalRaf;
});

function flushRaf() {
    // Flush all pending rAF callbacks (including nested ones)
    let safety = 10;
    while (rafCallbacks.length > 0 && safety-- > 0) {
        const batch = [...rafCallbacks];
        rafCallbacks = [];
        batch.forEach(cb => cb());
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAutoScroll", () => {
    describe("initial state", () => {
        test("starts at bottom with auto-scroll enabled", () => {
            const { result } = renderHook(() => useAutoScroll());

            expect(result.current.isAtBottom).toBe(true);
            expect(result.current.autoScrollEnabled).toBe(true);
            expect(result.current.userHasScrolled).toBe(false);
        });
    });

    describe("pauseAutoScroll", () => {
        test("disables auto-scroll and marks user as scrolled", () => {
            const { result } = renderHook(() => useAutoScroll());

            act(() => {
                result.current.pauseAutoScroll();
            });

            expect(result.current.isAtBottom).toBe(false);
            expect(result.current.autoScrollEnabled).toBe(false);
            expect(result.current.userHasScrolled).toBe(true);
        });

        test("clears isProgrammaticScroll after double-rAF so auto-scroll can resume", () => {
            const { result } = renderHook(() => useAutoScroll());

            // Provide a mock scroll element so scrollToBottom doesn't bail out
            act(() => {
                assignScrollRef(result);
            });

            act(() => {
                result.current.pauseAutoScroll();
            });

            expect(result.current.autoScrollEnabled).toBe(false);

            // Flush the double-rAF (outer + inner) to clear isProgrammaticScroll
            act(() => flushRaf());

            // autoScrollEnabled is still false (no scroll event re-enabled it),
            // but isProgrammaticScroll should be cleared. Verify by calling
            // scrollToBottom — if the flag were stuck, scrollToBottom's state
            // update would be blocked by content effects seeing isProgrammaticScroll.
            act(() => {
                result.current.scrollToBottom();
            });

            // scrollToBottom re-enables auto-scroll and sets isAtBottom
            expect(result.current.isAtBottom).toBe(true);
            expect(result.current.autoScrollEnabled).toBe(true);
        });

        test("handles rapid double-call without premature flag reset", () => {
            const { result } = renderHook(() => useAutoScroll());

            act(() => {
                result.current.pauseAutoScroll();
                result.current.pauseAutoScroll();
            });

            expect(result.current.autoScrollEnabled).toBe(false);

            // Flush only one rAF level — flag should still be set because counter is 2
            act(() => {
                const batch = [...rafCallbacks];
                rafCallbacks = [];
                batch.forEach(cb => cb());
            });

            // After one level, counter decremented but still > 0 for the second pause
            // Auto-scroll should still be disabled
            expect(result.current.autoScrollEnabled).toBe(false);
        });
    });

    describe("scrollToBottom", () => {
        test("re-enables auto-scroll and resets isAtBottom", () => {
            const { result } = renderHook(() => useAutoScroll());

            // Provide a mock scroll element so scrollToBottom doesn't bail out
            act(() => {
                assignScrollRef(result);
            });

            // First disable auto-scroll via pause
            act(() => {
                result.current.pauseAutoScroll();
            });
            expect(result.current.autoScrollEnabled).toBe(false);
            expect(result.current.isAtBottom).toBe(false);

            // Flush rAFs so isProgrammaticScroll clears
            act(() => flushRaf());

            // scrollToBottom should re-enable everything
            act(() => {
                result.current.scrollToBottom();
            });
            expect(result.current.autoScrollEnabled).toBe(true);
            expect(result.current.isAtBottom).toBe(true);
        });
    });

    describe("isProgrammaticScroll gate on content effects", () => {
        test("content height change during pauseAutoScroll does not trigger scrollToBottom", () => {
            // We track whether scrollToBottom is called by observing isAtBottom/autoScrollEnabled
            // after a content change while paused.
            const { result, rerender } = renderHook(({ content }) => useAutoScroll({ content }), { initialProps: { content: "initial" as React.ReactNode } });

            // Pause auto-scroll — this sets isProgrammaticScroll and disables autoScrollEnabled
            act(() => {
                result.current.pauseAutoScroll();
            });

            expect(result.current.autoScrollEnabled).toBe(false);
            expect(result.current.isAtBottom).toBe(false);

            // Trigger content change while paused (before rAF clears isProgrammaticScroll)
            rerender({ content: "updated content" as React.ReactNode });

            // Flush any pending rAFs from the content effect
            act(() => flushRaf());

            // autoScrollEnabled should still be false — the content effect should NOT
            // have called scrollToBottom because isProgrammaticScroll was true
            expect(result.current.autoScrollEnabled).toBe(false);
            expect(result.current.isAtBottom).toBe(false);
        });
    });

    describe("disableAutoScroll", () => {
        test("disables auto-scroll when not at bottom", () => {
            const { result } = renderHook(() => useAutoScroll());

            // When scrollRef has no element, checkIsAtBottom returns false,
            // so disableAutoScroll should disable auto-scroll
            act(() => {
                result.current.disableAutoScroll();
            });

            expect(result.current.autoScrollEnabled).toBe(false);
        });
    });
});
