import { useState, useEffect, type MutableRefObject } from "react";
import type { StreamingState } from "./useStreamingSpeed";

/**
 * Hook that runs an animation loop to smoothly advance through streaming content.
 * Uses the speed calculated by useStreamingSpeed to determine render pace.
 */
export function useStreamingAnimation(state: MutableRefObject<StreamingState>, contentRef: MutableRefObject<string>): string {
    const [displayedContent, setDisplayedContent] = useState("");

    useEffect(() => {
        let animationFrameId: number;
        let lastFrameTime = Date.now();

        const animate = () => {
            const now = Date.now();
            const dt = now - lastFrameTime;
            lastFrameTime = now;

            const s = state.current;
            const target = contentRef.current;

            // Handle content shrinking (e.g., reset)
            if (target.length < s.cursor) {
                s.cursor = target.length;
            }

            const backlog = target.length - s.cursor;

            if (backlog > 0) {
                // Linear advance at the calculated speed
                s.cursor += s.speed * dt;

                if (s.cursor > target.length) {
                    s.cursor = target.length;
                }

                setDisplayedContent(target.slice(0, Math.floor(s.cursor)));
            } else if (target.length > 0) {
                // Ensure final content is displayed
                setDisplayedContent(prev => (prev !== target ? target : prev));
            }

            animationFrameId = requestAnimationFrame(animate);
        };

        animationFrameId = requestAnimationFrame(animate);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [state, contentRef]);

    return displayedContent;
}
