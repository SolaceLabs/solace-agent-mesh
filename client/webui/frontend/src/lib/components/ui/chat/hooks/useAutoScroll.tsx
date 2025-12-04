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

    const [scrollState, setScrollState] = useState<ScrollState>({
        isAtBottom: true,
        autoScrollEnabled: true,
    });

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
            if (scrollState.autoScrollEnabled || autoScrollOnNewContent) {
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
            if (scrollState.autoScrollEnabled) {
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

    return {
        scrollRef,
        isAtBottom: scrollState.isAtBottom,
        autoScrollEnabled: scrollState.autoScrollEnabled,
        scrollToBottom: () => scrollToBottom(),
        disableAutoScroll,
        userHasScrolled: userHasScrolled.current,
    };
}
