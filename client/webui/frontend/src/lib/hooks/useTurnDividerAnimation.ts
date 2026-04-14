import { useCallback, useEffect, useLayoutEffect, useReducer, useRef } from "react";

import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

// Shared timing constants — keep in sync with CSS transitions in ChatPage.tsx
export const WAITING_DELAY_MS = 600;
export const SLIDE_OUT_DURATION_MS = 400;
export const FADE_OUT_DURATION_MS = 350;

interface AnimationState {
    isHistoryRevealed: boolean;
    isExitingHistory: boolean;
    isWaitingToExit: boolean;
}

type AnimationAction = { type: "DIVIDER_WAITING" } | { type: "DIVIDER_CHANGED" } | { type: "DIVIDER_REMOVED" } | { type: "SESSION_CHANGED" } | { type: "REVEAL_HISTORY" } | { type: "EXIT_COMPLETE" };

export function animationReducer(state: AnimationState, action: AnimationAction): AnimationState {
    switch (action.type) {
        case "DIVIDER_WAITING":
            return { isHistoryRevealed: false, isExitingHistory: false, isWaitingToExit: true };
        case "DIVIDER_CHANGED":
            return { isHistoryRevealed: false, isExitingHistory: true, isWaitingToExit: false };
        case "DIVIDER_REMOVED":
            return { ...state, isHistoryRevealed: false, isWaitingToExit: false };
        case "SESSION_CHANGED":
            return { isHistoryRevealed: false, isExitingHistory: false, isWaitingToExit: false };
        case "REVEAL_HISTORY":
            return { ...state, isHistoryRevealed: true };
        case "EXIT_COMPLETE":
            return { ...state, isExitingHistory: false };
        default:
            return state;
    }
}

interface UseTurnDividerAnimationOptions {
    turnDividerIndex: number | null;
    messagesLength: number;
    sessionId: string;
    chatMessageListRef: React.RefObject<ChatMessageListRef | null>;
}

export function useTurnDividerAnimation({ turnDividerIndex, messagesLength, sessionId, chatMessageListRef }: UseTurnDividerAnimationOptions) {
    const hasDivider = turnDividerIndex !== null && turnDividerIndex > 0 && turnDividerIndex < messagesLength;
    const [{ isHistoryRevealed, isExitingHistory, isWaitingToExit }, dispatch] = useReducer(animationReducer, {
        isHistoryRevealed: false,
        isExitingHistory: false,
        isWaitingToExit: false,
    });
    const newTurnAnchorRef = useRef<HTMLDivElement>(null);
    const lastDividerIndexRef = useRef<number | null>(null);
    // Tracks the previous divider index so during waiting we keep old collapse boundary
    const prevDividerIndexRef = useRef<number | null>(null);
    const oldScrollHeightRef = useRef<number | null>(null);
    const lastTouchYRef = useRef<number | null>(null);
    const prevSessionIdRef = useRef(sessionId);
    const needsScrollRef = useRef(false);

    const exitTimerRef = useRef<NodeJS.Timeout | null>(null);
    const exitDelayRef = useRef<NodeJS.Timeout | null>(null);
    // Tracks whether a session switch just happened — the next divider change
    // should skip the waiting delay and collapse immediately.
    const sessionJustSwitchedRef = useRef(false);

    // Synchronous derivation for the first render where the divider appears:
    // the reducer hasn't dispatched yet, so derive "waiting" state to keep old messages visible.
    // Only for new messages (not session switches).
    const sessionChanged = sessionId !== prevSessionIdRef.current;
    const dividerJustAppeared = hasDivider && turnDividerIndex !== lastDividerIndexRef.current && !sessionChanged;
    const effectiveIsWaiting = isWaitingToExit || (dividerJustAppeared && !sessionJustSwitchedRef.current);

    // The wrapper is always collapsed when there's a divider — only expanded by scroll-up reveal
    const isHistoryCollapsed = hasDivider && !isHistoryRevealed;
    // Whether the waiting phase is active (previous turn still visible before scroll-up)
    const isInWaitingPhase = effectiveIsWaiting;

    // During waiting AND exiting, collapse up to the PREVIOUS divider so the
    // previous turn stays in the DOM for the slide-up transition.
    // After exit completes, switch to the current divider index.
    const collapsedUpToIndex = (effectiveIsWaiting || isExitingHistory) && prevDividerIndexRef.current !== null ? prevDividerIndexRef.current : turnDividerIndex;

    // Sync refs and dispatch in useLayoutEffect — fires after DOM commit but
    // NOT during another component's render, so it's safe from error #301.
    useLayoutEffect(() => {
        let dispatched = false;
        if (sessionId !== prevSessionIdRef.current) {
            prevSessionIdRef.current = sessionId;
            lastDividerIndexRef.current = hasDivider ? turnDividerIndex : null;
            dispatch({ type: "SESSION_CHANGED" });
            // Only flag for session-switch path if the divider will arrive later
            // (e.g., from loadSessionTasks). If hasDivider is already true (first
            // message — session ID assigned in the same batch), the divider is
            // already handled above and won't trigger a separate change.
            sessionJustSwitchedRef.current = !hasDivider;
            if (exitDelayRef.current) {
                clearTimeout(exitDelayRef.current);
                exitDelayRef.current = null;
            }
            dispatched = true;
        }
        if (!dispatched && hasDivider && turnDividerIndex !== lastDividerIndexRef.current) {
            prevDividerIndexRef.current = lastDividerIndexRef.current;
            lastDividerIndexRef.current = turnDividerIndex;
            if (sessionJustSwitchedRef.current) {
                // Session switch — no animation, default state is already collapsed.
                // Scroll is handled by the needsScrollRef effect below (fires when anchor is in DOM).
                sessionJustSwitchedRef.current = false;
                needsScrollRef.current = true;
            } else {
                // New message — show at bottom first, then slide up after delay
                dispatch({ type: "DIVIDER_WAITING" });
                if (exitDelayRef.current) clearTimeout(exitDelayRef.current);
                exitDelayRef.current = setTimeout(() => {
                    // Trigger slide-up phase via DIVIDER_CHANGED (sets isExitingHistory)
                    dispatch({ type: "DIVIDER_CHANGED" });
                    // After the CSS transition completes, collapse and position
                    exitTimerRef.current = setTimeout(() => {
                        dispatch({ type: "EXIT_COMPLETE" });
                        chatMessageListRef.current?.pauseAutoScroll();
                        requestAnimationFrame(() => {
                            const container = chatMessageListRef.current?.scrollContainer;
                            const anchor = newTurnAnchorRef.current;
                            if (container && anchor) {
                                const prev = container.style.scrollBehavior;
                                container.style.scrollBehavior = "auto";
                                anchor.scrollIntoView({ block: "start" });
                                container.style.scrollBehavior = prev;
                            }
                            chatMessageListRef.current?.pauseAutoScroll();
                        });
                    }, SLIDE_OUT_DURATION_MS);
                }, WAITING_DELAY_MS);
            }
        }
        if (!dispatched && !hasDivider && lastDividerIndexRef.current !== null) {
            lastDividerIndexRef.current = null;
            dispatch({ type: "DIVIDER_REMOVED" });
        }
        return () => {
            if (exitDelayRef.current) {
                clearTimeout(exitDelayRef.current);
                exitDelayRef.current = null;
            }
        };
    }, [sessionId, turnDividerIndex, hasDivider]);

    // Reveal old messages when user scrolls up at the top (wheel, touch swipe, or keyboard).
    useEffect(() => {
        const container = chatMessageListRef.current?.scrollContainer;
        if (!container) return;

        const revealHistory = () => {
            oldScrollHeightRef.current = container.scrollHeight;
            chatMessageListRef.current?.pauseAutoScroll();
            dispatch({ type: "REVEAL_HISTORY" });
        };

        const handleWheel = (e: WheelEvent) => {
            if (e.deltaY < 0 && container.scrollTop <= 0 && isHistoryCollapsed) {
                revealHistory();
            }
        };

        const handleTouchStart = (e: TouchEvent) => {
            lastTouchYRef.current = e.touches[0]?.clientY ?? null;
        };

        const handleTouchMove = (e: TouchEvent) => {
            if (lastTouchYRef.current === null) return;
            const currentY = e.touches[0]?.clientY ?? 0;
            if (currentY > lastTouchYRef.current && container.scrollTop <= 0 && isHistoryCollapsed) {
                revealHistory();
            }
            lastTouchYRef.current = currentY;
        };

        const handleKeyDown = (e: KeyboardEvent) => {
            const isScrollUpKey = e.key === "PageUp" || e.key === "Home";
            if (isScrollUpKey && container.scrollTop <= 0 && isHistoryCollapsed) {
                revealHistory();
            }
        };

        container.addEventListener("wheel", handleWheel, { passive: true });
        container.addEventListener("touchstart", handleTouchStart, { passive: true });
        container.addEventListener("touchmove", handleTouchMove, { passive: true });
        container.addEventListener("keydown", handleKeyDown);
        return () => {
            container.removeEventListener("wheel", handleWheel);
            container.removeEventListener("touchstart", handleTouchStart);
            container.removeEventListener("touchmove", handleTouchMove);
            container.removeEventListener("keydown", handleKeyDown);
        };
    }, [isHistoryCollapsed, chatMessageListRef]);

    // After history expands in the DOM, adjust scrollTop to keep current turn in place.
    useLayoutEffect(() => {
        if (isHistoryRevealed && oldScrollHeightRef.current !== null) {
            const container = chatMessageListRef.current?.scrollContainer;
            if (container) {
                const addedHeight = container.scrollHeight - oldScrollHeightRef.current;
                if (addedHeight > 0) {
                    // Step 1: instant jump to keep current turn in place (no flash)
                    const prev = container.style.scrollBehavior;
                    container.style.scrollBehavior = "auto";
                    container.scrollTop = addedHeight;
                    container.style.scrollBehavior = prev;
                    // Step 2: smooth scroll up to reveal old messages gliding in from above
                    requestAnimationFrame(() => {
                        container.scrollTo({ top: Math.max(0, addedHeight - 300), behavior: "smooth" });
                    });
                }
            }
            oldScrollHeightRef.current = null;
        }
    }, [isHistoryRevealed, chatMessageListRef]);

    // Scroll to the new turn anchor after a session switch.
    // Runs on every render (no deps) to catch the moment the anchor appears in the DOM.
    const scrollToAnchor = useCallback(() => {
        const container = chatMessageListRef.current?.scrollContainer;
        const anchor = newTurnAnchorRef.current;
        if (container && anchor) {
            const prev = container.style.scrollBehavior;
            container.style.scrollBehavior = "auto";
            anchor.scrollIntoView({ block: "start" });
            container.style.scrollBehavior = prev;
        }
    }, [chatMessageListRef]);

    // No dependency array: must run every render because the anchor element may not
    // exist in the DOM until a subsequent render after needsScrollRef is set. Once
    // needsScrollRef is consumed (set to false), the body is a no-op on future renders.
    useLayoutEffect(() => {
        if (needsScrollRef.current && isHistoryCollapsed && newTurnAnchorRef.current) {
            needsScrollRef.current = false;
            // Position before paint
            chatMessageListRef.current?.pauseAutoScroll();
            scrollToAnchor();
            // Re-position after auto-scroll effects fire (they run after layout effects)
            // Use escalating delays to catch ResizeObserver and content effects
            requestAnimationFrame(() => {
                chatMessageListRef.current?.pauseAutoScroll();
                scrollToAnchor();
                requestAnimationFrame(() => {
                    chatMessageListRef.current?.pauseAutoScroll();
                    scrollToAnchor();
                });
            });
        }
    });

    return {
        hasDivider,
        isHistoryCollapsed,
        isExitingHistory,
        isHistoryRevealed,
        isInWaitingPhase,
        newTurnAnchorRef,
        collapsedUpToIndex,
    };
}
