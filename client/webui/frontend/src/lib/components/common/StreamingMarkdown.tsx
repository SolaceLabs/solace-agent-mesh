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
                // User requirement: Target rendering time = 120% of chunk arrival period.
                // This intentionally slows down rendering to build a buffer and bridge gaps.
                const arrivalRate = added / dt;
                const targetSpeed = arrivalRate / 1.2;

                // Smooth the speed update: 70% old, 30% new
                const newSpeed = s.speed * 0.7 + targetSpeed * 0.3;
                
                // Clamp speed to reasonable human-readable bounds
                s.speed = Math.max(0.01, Math.min(1.5, newSpeed));
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

                // Catch-up mechanism: If backlog is large, boost speed gently.
                // Start boosting when backlog > 30 chars.
                // Formula ensures continuous acceleration rather than a hard step.
                // e.g. backlog 30 -> 1.0x, backlog 80 -> 1.5x, backlog 130 -> 2.0x
                const boost = 1 + Math.max(0, (backlog - 30) / 100);
                currentSpeed *= boost;

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
