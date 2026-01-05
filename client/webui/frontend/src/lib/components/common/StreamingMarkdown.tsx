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
        cursor: isStreaming ? 0 : content.length,
        speed: 0.03, // Initial conservative speed (30 chars/sec)
        lastArrivalTime: 0, // Initialize to 0 to detect first chunk
        avgInterval: 500, // Estimate 500ms between chunks initially
        lastLen: isStreaming ? 0 : content.length,
    });

    const contentRef = useRef(content);

    useEffect(() => {
        contentRef.current = content;
        
        if (isStreaming) {
            const now = Date.now();
            const s = state.current;
            const added = content.length - s.lastLen;
            
            if (added > 0) {
                if (s.lastArrivalTime === 0) {
                    // First chunk received
                    s.lastArrivalTime = now;
                    // No interval to calculate yet
                } else {
                    // Calculate time since last chunk
                    let dt = now - s.lastArrivalTime;
                    
                    // Safety: Clamp dt to avoid extreme spikes from jitter or initial mount
                    dt = Math.max(20, Math.min(5000, dt));

                    // Update moving average of inter-arrival time
                    const alpha = dt < 200 ? 0.05 : 0.2;
                    s.avgInterval = s.avgInterval * (1 - alpha) + dt * alpha;
                    
                    s.lastArrivalTime = now;
                }

                // Calculate target speed based on clearing the TOTAL backlog over the next interval (+50% buffer)
                const backlog = content.length - s.cursor;
                // Increased safety factor to 1.5 to better bridge jittery gaps
                const targetSpeed = backlog / (s.avgInterval * 1.5);

                // Update current speed smoothly
                const momentum = targetSpeed > s.speed ? 0.5 : 0.8;
                s.speed = s.speed * momentum + targetSpeed * (1 - momentum);
                
                // Hard clamps to keep it sane
                s.speed = Math.max(0.005, Math.min(3.0, s.speed));

                s.lastLen = content.length;
            }
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
            
            if (target.length < s.cursor) {
                s.cursor = target.length;
            }

            const backlog = target.length - s.cursor;

            if (backlog > 0) {
                // Simple linear advance at the calculated speed
                s.cursor += s.speed * dt;

                if (s.cursor > target.length) {
                    s.cursor = target.length;
                }

                setDisplayedContent(target.slice(0, Math.floor(s.cursor)));
            } else if (backlog <= 0 && target.length > 0 && displayedContent.length !== target.length) {
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
