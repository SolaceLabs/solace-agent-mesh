import { useEffect, useLayoutEffect, useReducer, useRef } from "react";

import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

const SLIDE_OUT_DURATION_MS = 500;

interface AnimationState {
    isHistoryRevealed: boolean;
    isExitingHistory: boolean;
}

type AnimationAction = { type: "DIVIDER_CHANGED" } | { type: "DIVIDER_REMOVED" } | { type: "SESSION_CHANGED" } | { type: "REVEAL_HISTORY" } | { type: "EXIT_COMPLETE" };

export function animationReducer(state: AnimationState, action: AnimationAction): AnimationState {
    switch (action.type) {
        case "DIVIDER_CHANGED":
            return !state.isHistoryRevealed && state.isExitingHistory ? state : { isHistoryRevealed: false, isExitingHistory: true };
        case "DIVIDER_REMOVED":
            return !state.isHistoryRevealed ? state : { isHistoryRevealed: false, isExitingHistory: state.isExitingHistory };
        case "SESSION_CHANGED":
            return !state.isHistoryRevealed && !state.isExitingHistory ? state : { isHistoryRevealed: false, isExitingHistory: false };
        case "REVEAL_HISTORY":
            return state.isHistoryRevealed ? state : { ...state, isHistoryRevealed: true };
        case "EXIT_COMPLETE":
            return !state.isExitingHistory ? state : { ...state, isExitingHistory: false };
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
    const [{ isHistoryRevealed, isExitingHistory }, dispatch] = useReducer(animationReducer, {
        isHistoryRevealed: false,
        isExitingHistory: false,
    });
    const newTurnAnchorRef = useRef<HTMLDivElement>(null);
    const lastDividerIndexRef = useRef<number | null>(null);
    const exitTimerRef = useRef<NodeJS.Timeout | null>(null);
    const historyWrapperRef = useRef<HTMLDivElement>(null);
    const oldScrollHeightRef = useRef<number | null>(null);
    const lastTouchYRef = useRef<number | null>(null);
    const prevSessionIdRef = useRef(sessionId);

    // Derive transition flags synchronously — no dispatch during render to avoid
    // React error #301 ("Cannot update a component while rendering a different component").
    const sessionChanged = sessionId !== prevSessionIdRef.current;
    const dividerChanged = hasDivider && turnDividerIndex !== lastDividerIndexRef.current;

    // On the first render where the divider appears, the reducer hasn't been
    // dispatched yet (isExitingHistory is still false). Derive the effective
    // value so the animation class is applied on the very first paint.
    const effectiveIsExiting = isExitingHistory || (dividerChanged && !sessionChanged);
    const effectiveIsRevealed = sessionChanged ? false : isHistoryRevealed;

    const isHistoryCollapsed = hasDivider && !effectiveIsExiting && !effectiveIsRevealed;

    // Sync refs and dispatch in useLayoutEffect — fires after DOM commit but
    // NOT during another component's render, so it's safe from error #301.
    useLayoutEffect(() => {
        let dispatched = false;
        if (sessionId !== prevSessionIdRef.current) {
            prevSessionIdRef.current = sessionId;
            // Preserve the divider ref if still active — avoids re-triggering
            // the exit animation when sessionId first gets assigned (empty → real).
            lastDividerIndexRef.current = hasDivider ? turnDividerIndex : null;
            dispatch({ type: "SESSION_CHANGED" });
            dispatched = true;
        }
        if (!dispatched && hasDivider && turnDividerIndex !== lastDividerIndexRef.current) {
            lastDividerIndexRef.current = turnDividerIndex;
            dispatch({ type: "DIVIDER_CHANGED" });
        }
        if (!dispatched && !hasDivider && lastDividerIndexRef.current !== null) {
            lastDividerIndexRef.current = null;
            dispatch({ type: "DIVIDER_REMOVED" });
        }
    }, [sessionId, turnDividerIndex, hasDivider]);

    // Schedule the animation end callback after isExitingHistory is set synchronously above
    useEffect(() => {
        if (!isExitingHistory || !hasDivider) return;

        const onExitComplete = () => {
            dispatch({ type: "EXIT_COMPLETE" });
            const pausePromise = chatMessageListRef.current?.pauseAutoScroll();
            requestAnimationFrame(() => {
                newTurnAnchorRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
                // Re-engage auto-scroll after the pause has settled so the
                // streaming response is followed without racing the double-rAF
                // in pauseAutoScroll that clears isProgrammaticScroll.
                if (pausePromise) {
                    pausePromise.then(() => {
                        chatMessageListRef.current?.scrollToBottom();
                    });
                } else {
                    chatMessageListRef.current?.scrollToBottom();
                }
            });
        };

        const wrapper = historyWrapperRef.current;
        let activeHandler: (() => void) | null = null;

        if (wrapper) {
            const handler = () => {
                wrapper.removeEventListener("animationend", handler);
                activeHandler = null;
                if (exitTimerRef.current) {
                    clearTimeout(exitTimerRef.current);
                    exitTimerRef.current = null;
                }
                onExitComplete();
            };
            activeHandler = handler;
            wrapper.addEventListener("animationend", handler, { once: true });
            exitTimerRef.current = setTimeout(() => {
                wrapper.removeEventListener("animationend", handler);
                activeHandler = null;
                onExitComplete();
            }, SLIDE_OUT_DURATION_MS + 100);
        } else {
            exitTimerRef.current = setTimeout(onExitComplete, SLIDE_OUT_DURATION_MS);
        }

        return () => {
            if (exitTimerRef.current) clearTimeout(exitTimerRef.current);
            if (activeHandler && wrapper) wrapper.removeEventListener("animationend", activeHandler);
        };
    }, [isExitingHistory, hasDivider, chatMessageListRef]);

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
                    container.scrollTo({ top: addedHeight, behavior: "instant" });
                }
            }
            oldScrollHeightRef.current = null;
        }
    }, [isHistoryRevealed, chatMessageListRef]);

    return {
        hasDivider,
        isHistoryCollapsed,
        isExitingHistory: effectiveIsExiting,
        isHistoryRevealed: effectiveIsRevealed,
        historyWrapperRef,
        newTurnAnchorRef,
        SLIDE_OUT_DURATION_MS,
    };
}
