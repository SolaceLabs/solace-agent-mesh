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
            minInterval: Infinity,
            maxInterval: 0,
            bufferUnderruns: 0,
            totalChars: 0,
            maxBacklog: 0,
            avgJitter: 0,
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
                const avgChunkSize = (s.stats.totalChars / s.stats.chunks).toFixed(1);
                
                console.log(
                    `[StreamingMarkdown Stats] Chunks: ${s.stats.chunks}, ` +
                    `Avg Interval: ${avgArrival}ms (Range: ${s.stats.minInterval.toFixed(0)}-${s.stats.maxInterval.toFixed(0)}ms), ` +
                    `Avg Jitter: ${s.stats.avgJitter.toFixed(0)}ms, ` +
                    `Avg Chunk: ${avgChunkSize} chars, Max Backlog: ${s.stats.maxBacklog}, ` +
                    `Render Time: ${s.stats.renderTime.toFixed(0)}ms, ` +
                    `Pause Time: ${s.stats.pauseTime.toFixed(0)}ms ` +
                    `(${percentPaused}% paused, ${s.stats.bufferUnderruns} underruns)`
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
                s.stats.totalChars += added;
                s.stats.minInterval = Math.min(s.stats.minInterval, dt);
                s.stats.maxInterval = Math.max(s.stats.maxInterval, dt);

                const jitter = Math.abs(dt - s.avgInterval);
                s.stats.avgJitter = s.stats.avgJitter * 0.8 + jitter * 0.2;

                // Safety: Clamp dt to avoid extreme spikes from jitter or initial mount
                dt = Math.max(20, Math.min(5000, dt));

                // Update moving average of inter-arrival time
                // Use a slower alpha for very fast chunks (likely bunched) to prevent speed spikes
                const alpha = dt < 200 ? 0.05 : 0.2;
                s.avgInterval = s.avgInterval * (1 - alpha) + dt * alpha;

                // Calculate target speed based on clearing the TOTAL backlog over the next interval (+50% buffer)
                const backlog = content.length - s.cursor;
                // Increased safety factor to 1.5 to better bridge jittery gaps
                const targetSpeed = backlog / (s.avgInterval * 1.5);

                // Update current speed with very high momentum for smooth transitions
                s.speed = s.speed * 0.9 + targetSpeed * 0.1;
                
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
        let wasPaused = false;

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
            s.stats.maxBacklog = Math.max(s.stats.maxBacklog, Math.floor(backlog));

            if (backlog > 0) {
                wasPaused = false;
                // Track render time
                s.stats.renderTime += dt;

                // Simple linear advance at the calculated speed
                s.cursor += s.speed * dt;

                if (s.cursor > target.length) {
                    s.cursor = target.length;
                }

                setDisplayedContent(target.slice(0, Math.floor(s.cursor)));
            } else if (backlog <= 0) {
                if (!wasPaused) {
                    s.stats.bufferUnderruns++;
                    wasPaused = true;
                }
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
