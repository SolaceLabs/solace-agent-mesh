import { useCallback, useEffect, useRef, useState } from "react";

interface ScrollState {
    isAtBottom: boolean;
    autoScrollEnabled: boolean;
}

interface UseAutoScrollOptions {
    offset?: number;
    smooth?: boolean;
    content?: React.ReactNode;
    autoScrollOnNewContent?: boolean;
    contentRef?: React.RefObject<HTMLElement | null>;
}

export function useAutoScroll(options: UseAutoScrollOptions = {}) {
    const { offset = 20, smooth = false, content, autoScrollOnNewContent = false, contentRef } = options;
    const scrollRef = useRef<HTMLDivElement>(null);
    const lastContentHeight = useRef(0);
    const userHasScrolled = useRef(false);
    const lastScrollTop = useRef(0);
    const recentUpwardScroll = useRef(false);
    const isProgrammaticScroll = useRef(false);
    const programmaticScrollCount = useRef(0);
    const unmountedRef = useRef(false);

    const [scrollState, setScrollState] = useState<ScrollState>({
        isAtBottom: true,
        autoScrollEnabled: true,
    });

    // Reset programmatic scroll state on unmount to prevent stale refs
    useEffect(() => {
        unmountedRef.current = false;
        return () => {
            unmountedRef.current = true;
            programmaticScrollCount.current = 0;
            isProgrammaticScroll.current = false;
        };
    }, []);

    const checkIsAtBottom = useCallback(
        (element: HTMLElement) => {
            const { scrollTop, scrollHeight, clientHeight } = element;
            const distanceToBottom = Math.abs(scrollHeight - scrollTop - clientHeight);
            return distanceToBottom <= offset;
        },
        [offset]
    );

    const scrollToBottom = useCallback(
        (instant?: boolean) => {
            if (!scrollRef.current) return;

            // Mark as programmatic scroll to prevent interference
            isProgrammaticScroll.current = true;

            const targetScrollTop = scrollRef.current.scrollHeight - scrollRef.current.clientHeight;

            if (instant) {
                scrollRef.current.scrollTop = targetScrollTop;
            } else {
                scrollRef.current.scrollTo({
                    top: targetScrollTop,
                    behavior: smooth ? "smooth" : "auto",
                });
            }

            // Clear upward scroll flag - we're going to bottom, re-enable auto-scroll
            recentUpwardScroll.current = false;

            setScrollState({
                isAtBottom: true,
                autoScrollEnabled: true,
            });
            userHasScrolled.current = false;

            // Clear the programmatic scroll flag after animation completes
            // Update lastScrollTop after the animation to prevent false detection
            setTimeout(
                () => {
                    if (scrollRef.current) {
                        lastScrollTop.current = scrollRef.current.scrollTop;
                    }
                    isProgrammaticScroll.current = false;
                },
                instant ? 50 : 500
            );
        },
        [smooth]
    );

    const handleScroll = useCallback(() => {
        if (!scrollRef.current) return;

        // Ignore scroll events during programmatic scrolling
        if (isProgrammaticScroll.current) {
            return;
        }

        const currentScrollTop = scrollRef.current.scrollTop;
        const atBottom = checkIsAtBottom(scrollRef.current);

        // Detect scroll direction (only if we have a previous position)
        const isScrollingUp = lastScrollTop.current > 0 && currentScrollTop < lastScrollTop.current;

        // Simple rule: upward scroll = disable, at bottom = enable
        if (isScrollingUp) {
            // User scrolled up - disable auto-scroll
            recentUpwardScroll.current = true;
        }

        // Update last scroll position
        lastScrollTop.current = currentScrollTop;

        // Determine auto-scroll state:
        // - If at bottom: always enable (clear the upward scroll flag)
        // - If not at bottom and user scrolled up recently: disable
        // - Otherwise: keep previous state
        if (atBottom) {
            // At bottom - always enable and clear the flag
            recentUpwardScroll.current = false;
            setScrollState(() => ({
                isAtBottom: true,
                autoScrollEnabled: true,
            }));
        } else if (recentUpwardScroll.current) {
            // Not at bottom and user has scrolled up - disable
            setScrollState(() => ({
                isAtBottom: false,
                autoScrollEnabled: false,
            }));
        } else {
            // Not at bottom but no recent upward scroll - just update position
            setScrollState(prev => ({
                ...prev,
                isAtBottom: false,
            }));
        }
    }, [checkIsAtBottom]);

    useEffect(() => {
        const element = scrollRef.current;
        if (!element) return;

        element.addEventListener("scroll", handleScroll, { passive: true });
        return () => element.removeEventListener("scroll", handleScroll);
    }, [handleScroll]);

    useEffect(() => {
        const scrollElement = scrollRef.current;
        if (!scrollElement) return;

        const currentHeight = scrollElement.scrollHeight;
        const hasNewContent = currentHeight !== lastContentHeight.current;

        if (hasNewContent) {
            if ((scrollState.autoScrollEnabled || autoScrollOnNewContent) && !isProgrammaticScroll.current) {
                requestAnimationFrame(() => {
                    scrollToBottom(lastContentHeight.current === 0);
                });
            }
            lastContentHeight.current = currentHeight;
        }
    }, [content, scrollState.autoScrollEnabled, scrollToBottom, autoScrollOnNewContent]);

    useEffect(() => {
        // Observe the content element (where messages are) instead of scroll container
        // This ensures we detect when artifacts expand/collapse and adjust scroll
        const element = contentRef?.current || scrollRef.current;
        if (!element) return;

        const resizeObserver = new ResizeObserver(() => {
            if (scrollState.autoScrollEnabled && !isProgrammaticScroll.current) {
                scrollToBottom(true);
            }
        });

        resizeObserver.observe(element);
        return () => resizeObserver.disconnect();
    }, [scrollState.autoScrollEnabled, scrollToBottom, contentRef]);

    const disableAutoScroll = useCallback(() => {
        const atBottom = scrollRef.current ? checkIsAtBottom(scrollRef.current) : false;

        // Only disable if not at bottom
        if (!atBottom) {
            userHasScrolled.current = true;
            setScrollState(prev => ({
                ...prev,
                autoScrollEnabled: false,
            }));
        }
    }, [checkIsAtBottom]);

    // Synchronously block auto-scroll for the next render cycle.
    // Sets isProgrammaticScroll (checked by content & resize effects)
    // and disables autoScrollEnabled via state.
    // The flag is cleared after layout settles via requestAnimationFrame, which fires
    // after the browser has completed layout and paint — unlike a fixed timeout this
    // adapts to slow devices and heavy DOM updates.
    // Pauses auto-scroll until the browser has completed layout and paint
    // (double-rAF). Returns a Promise that resolves once the pause has
    // fully settled, so callers can chain follow-up scroll actions without
    // guessing rAF nesting depth.
    //
    // Concurrency: programmaticScrollCount acts as a semaphore — each call
    // increments it, and the inner rAF decrements. isProgrammaticScroll is
    // only cleared when all concurrent pauses have settled (count reaches 0).
    const pauseAutoScroll = useCallback((): Promise<void> => {
        programmaticScrollCount.current += 1;
        isProgrammaticScroll.current = true;
        setScrollState({ isAtBottom: false, autoScrollEnabled: false });
        userHasScrolled.current = true;
        return new Promise<void>(resolve => {
            requestAnimationFrame(() => {
                // Double-rAF ensures the scroll position is stable after both layout and paint
                requestAnimationFrame(() => {
                    if (unmountedRef.current) {
                        resolve();
                        return;
                    }
                    if (scrollRef.current) {
                        lastScrollTop.current = scrollRef.current.scrollTop;
                        lastContentHeight.current = scrollRef.current.scrollHeight;
                    }
                    programmaticScrollCount.current -= 1;
                    if (programmaticScrollCount.current <= 0) {
                        programmaticScrollCount.current = 0;
                        isProgrammaticScroll.current = false;
                    }
                    resolve();
                });
            });
        });
    }, []);

    return {
        scrollRef,
        isAtBottom: scrollState.isAtBottom,
        autoScrollEnabled: scrollState.autoScrollEnabled,
        scrollToBottom: () => scrollToBottom(),
        disableAutoScroll,
        pauseAutoScroll,
        userHasScrolled: userHasScrolled.current,
    };
}
