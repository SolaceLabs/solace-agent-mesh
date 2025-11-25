import { useState, useEffect, useRef } from "react";

/**
 * Hook that animates text with a typewriter effect
 * @param finalText - The final text to display
 * @param speed - Milliseconds per character (default: 30)
 * @returns The current animated text
 */
export const useTypewriterEffect = (finalText: string, speed: number = 30): string => {
    const [displayedText, setDisplayedText] = useState("");
    const previousTextRef = useRef("");

    useEffect(() => {
        // If text hasn't changed, don't animate
        if (finalText === previousTextRef.current) {
            return;
        }

        // Reset to empty and start animation
        setDisplayedText("");
        previousTextRef.current = finalText;

        if (!finalText) {
            return;
        }

        let currentIndex = 0;
        const intervalId = setInterval(() => {
            if (currentIndex < finalText.length) {
                setDisplayedText(finalText.substring(0, currentIndex + 1));
                currentIndex++;
            } else {
                clearInterval(intervalId);
            }
        }, speed);

        return () => clearInterval(intervalId);
    }, [finalText, speed]);

    return displayedText || finalText;
};
