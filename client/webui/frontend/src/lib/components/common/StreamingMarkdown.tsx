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
        lastArrivalTime: Date.now(),
        avgInterval: 500, // Estimate 500ms between chunks initially
        lastLen: isStreaming ? 0 : content.length,
        // Performance metrics
        stats: {
            chunks: 0,
            totalInterval: 0,
            renderTime: 0,
            pauseTime: 0,
        }
    });

    const contentRef = useRef(content);

    // Logging effect: Log stats when the component unmounts (streaming ends)
    useEffect(() => {
        return () => {
            const s = state.current;
            if (s.stats.chunks > 0) {
                const totalTime = s.stats.renderTime + s.stats.pauseTime;
                const percentPaused = totalTime > 0 ? ((s.stats.pauseTime / totalTime) * 100).toFixed(1) : "0.0";
                const avgArrival = (s.stats.totalInterval / s.stats.chunks).toFixed(0);
                
                console.log(
                    `[StreamingMarkdown Stats] Chunks: ${s.stats.chunks}, ` +
                    `Avg Interval: ${avgArrival}ms, ` +
                    `Render Time: ${s.stats.renderTime.toFixed(0)}ms, ` +
                    `Pause Time: ${s.stats.pauseTime.toFixed(0)}ms ` +
                    `(${percentPaused}% paused)`
                );
            }
        };
    }, []);

    useEffect(() => {
        contentRef.current = content;
        
        if (isStreaming) {
            const now = Date.now();
            const s = state.current;
            const added = content.length - s.lastLen;
            
            if (added > 0) {
                // Calculate time since last chunk
                let dt = now - s.lastArrivalTime;
                
                // Update stats
                s.stats.chunks++;
                s.stats.totalInterval += dt;

                // Safety: Clamp dt to avoid extreme spikes from jitter or initial mount
                // Min 20ms (50fps) to prevent division by zero or massive rates on rapid-fire updates
                // Max 5000ms to prevent one long pause from skewing the average forever
                dt = Math.max(20, Math.min(5000, dt));

                // Update moving average of inter-arrival time
                // Slower adaptation (80/20) to filter out jitter
                s.avgInterval = s.avgInterval * 0.8 + dt * 0.2;

                // Calculate target speed based on clearing the TOTAL backlog over the next interval (+20% buffer)
                const backlog = content.length - s.cursor;
                // We want to finish the current backlog roughly when the next chunk is expected, plus a bit.
                const targetSpeed = backlog / (s.avgInterval * 1.2);

                // Update current speed smoothly
                // If we need to speed up, do it faster (react to burst). 
                // If slowing down, do it gradually.
                const momentum = targetSpeed > s.speed ? 0.5 : 0.8;
                s.speed = s.speed * momentum + targetSpeed * (1 - momentum);
                
                // Hard clamps to keep it sane
                s.speed = Math.max(0.005, Math.min(3.0, s.speed));

                s.lastArrivalTime = now;
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
                // Track render time
                s.stats.renderTime += dt;

                // Simple linear advance at the calculated speed
                s.cursor += s.speed * dt;

                if (s.cursor > target.length) {
                    s.cursor = target.length;
                }

                setDisplayedContent(target.slice(0, Math.floor(s.cursor)));
            } else if (backlog <= 0) {
                // Track pause time (waiting for chunks)
                s.stats.pauseTime += dt;
                
                if (target.length > 0 && displayedContent.length !== target.length) {
                    setDisplayedContent(target);
                }
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
