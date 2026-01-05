import React, { useState, useEffect, useRef } from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";

interface StreamingMarkdownProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
}

export const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({ content, isStreaming, className }) => {
    const [displayedContent, setDisplayedContent] = useState(isStreaming ? "" : content);
    
    // Use refs for mutable state to avoid re-renders during calculations
    const state = useRef({
        cursor: isStreaming ? 0 : content.length, // Current float position in displayed text
        speed: 0.05, // Initial speed: 0.05 chars/ms = 50 chars/sec (approx 20ms per char)
        lastUpdate: Date.now(),
        lastLen: isStreaming ? 0 : content.length,
    });

    const contentRef = useRef(content);

    useEffect(() => {
        contentRef.current = content;
        
        // Adaptive speed calculation
        if (isStreaming) {
            const now = Date.now();
            const s = state.current;
            const added = content.length - s.lastLen;
            const dt = now - s.lastUpdate;

            // Only update speed if we received data and some time has passed
            if (added > 0 && dt > 0) {
                const instantRate = added / dt;
                // Smooth the speed update: 70% old, 30% new to reduce jitter
                // We use a moving average to adapt to the stream rate
                const newSpeed = s.speed * 0.7 + instantRate * 0.3;
                
                // Clamp speed to reasonable human-readable bounds
                // Min: 0.02 (~20 chars/s) - prevents stalling on slow connections
                // Max: 1.0 (~1000 chars/s) - prevents epilepsy on huge bursts
                s.speed = Math.max(0.02, Math.min(1.0, newSpeed));
            }

            s.lastUpdate = now;
            s.lastLen = content.length;
        }
    }, [content, isStreaming]);

    useEffect(() => {
        if (!isStreaming) {
            setDisplayedContent(content);
            state.current.cursor = content.length;
            state.current.lastLen = content.length;
            return;
        }

        let animationFrameId: number;
        let lastFrameTime = Date.now();

        const animate = () => {
            const now = Date.now();
            const dt = now - lastFrameTime;
            lastFrameTime = now;

            const s = state.current;
            const target = contentRef.current;
            
            // Correction: If content shrank (reset?), reset cursor
            if (target.length < s.cursor) {
                s.cursor = target.length;
            }

            const backlog = target.length - s.cursor;

            if (backlog > 0) {
                // Base speed from our adaptive rate
                let currentSpeed = s.speed;

                // Catch-up mechanism: If backlog is large, boost speed
                // If we are 100 chars behind, we should hurry up.
                // Boost factor increases linearly with backlog.
                if (backlog > 50) {
                    currentSpeed *= 1 + (backlog / 100); 
                }

                // Advance cursor
                s.cursor += currentSpeed * dt;

                // Clamp to actual content length
                if (s.cursor > target.length) {
                    s.cursor = target.length;
                }

                // Update display
                const newLength = Math.floor(s.cursor);
                setDisplayedContent(target.slice(0, newLength));
            } else if (backlog <= 0 && target.length > 0 && displayedContent.length !== target.length) {
                // Ensure we exactly match the end if we overshot or are close enough
                setDisplayedContent(target);
            }

            animationFrameId = requestAnimationFrame(animate);
        };

        animationFrameId = requestAnimationFrame(animate);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [isStreaming]); // content dependency removed from effect, accessed via ref

    return <MarkdownHTMLConverter className={className}>{displayedContent}</MarkdownHTMLConverter>;
};
