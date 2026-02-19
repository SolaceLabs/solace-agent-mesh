import { useState, useEffect, useRef } from "react";

/**
 * Hook that animates text with a subtle pulse and fade-in effect.
 * Also listens for session-title-generating events to show a slow pulse
 * while AI is generating a title.
 * @param finalText - The final text to display
 * @param sessionId - Optional session ID to track title generation for
 * @returns Object with displayedText, isAnimating flag, and isGenerating flag
 */
export const useTitleAnimation = (finalText: string, sessionId?: string): { text: string; isAnimating: boolean; isGenerating: boolean } => {
    const [displayedText, setDisplayedText] = useState(finalText);
    const [isAnimating, setIsAnimating] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const previousTextRef = useRef(finalText);
    const previousSessionIdRef = useRef(sessionId);
    const wasGeneratingRef = useRef(false);

    // Listen for title generation events
    useEffect(() => {
        if (!sessionId) return;

        const handleTitleGenerating = (event: Event) => {
            const customEvent = event as CustomEvent;
            const { sessionId: eventSessionId, isGenerating: generating } = customEvent.detail;

            if (eventSessionId === sessionId) {
                setIsGenerating(generating);
                if (generating) {
                    wasGeneratingRef.current = true;
                }
            }
        };

        window.addEventListener("session-title-generating", handleTitleGenerating);
        return () => {
            window.removeEventListener("session-title-generating", handleTitleGenerating);
        };
    }, [sessionId]);

    useEffect(() => {
        const sessionChanged = sessionId !== previousSessionIdRef.current;
        const textChanged = finalText !== previousTextRef.current;

        // Update session ref immediately
        previousSessionIdRef.current = sessionId;

        // If session changed, just update text immediately without animation
        if (sessionChanged) {
            previousTextRef.current = finalText;
            setDisplayedText(finalText);
            setIsAnimating(false);
            // Reset generating state for new session
            setIsGenerating(false);
            wasGeneratingRef.current = false;
            return;
        }

        // If text hasn't changed, don't do anything
        if (!textChanged) {
            return;
        }

        // Only animate if we were in a generating state (title was being generated)
        // This prevents animation when switching sessions
        const shouldAnimate = wasGeneratingRef.current;

        // Stop generating state when text changes (title was generated)
        if (isGenerating) {
            setIsGenerating(false);
        }

        if (!finalText) {
            previousTextRef.current = finalText;
            setDisplayedText("");
            setIsAnimating(false);
            wasGeneratingRef.current = false;
            return;
        }

        if (shouldAnimate) {
            setIsAnimating(true);

            // Wait a brief moment for pulse animation, then update text
            const timer = setTimeout(() => {
                // Update ref and display text together
                previousTextRef.current = finalText;
                setDisplayedText(finalText);
                // Keep animating flag true for fade-in animation
                setTimeout(() => {
                    setIsAnimating(false);
                    wasGeneratingRef.current = false;
                }, 300);
            }, 200);

            return () => clearTimeout(timer);
        } else {
            // No animation - just update text immediately
            previousTextRef.current = finalText;
            setDisplayedText(finalText);
        }
    }, [finalText, sessionId, isGenerating]);

    return { text: displayedText, isAnimating, isGenerating };
};
