import { useState, useEffect, useRef } from "react";

/**
 * Hook that animates text with a subtle pulse and fade-in effect
 * @param finalText - The final text to display
 * @returns Object with displayedText and isAnimating flag
 */
export const useTitleAnimation = (finalText: string): { text: string; isAnimating: boolean } => {
    const [displayedText, setDisplayedText] = useState(finalText);
    const [isAnimating, setIsAnimating] = useState(false);
    const previousTextRef = useRef(finalText);

    useEffect(() => {
        // If text hasn't changed, don't animate
        if (finalText === previousTextRef.current) {
            return;
        }

        // Start animation
        setIsAnimating(true);
        previousTextRef.current = finalText;

        if (!finalText) {
            setDisplayedText("");
            setIsAnimating(false);
            return;
        }

        // Wait a brief moment for pulse animation, then update text
        const timer = setTimeout(() => {
            setDisplayedText(finalText);
            // Keep animating flag true for fade-in animation
            setTimeout(() => {
                setIsAnimating(false);
            }, 300);
        }, 200);

        return () => clearTimeout(timer);
    }, [finalText]);

    return { text: displayedText, isAnimating };
};
