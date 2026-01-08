import React, { useState, useEffect, useRef } from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";
import * as StreamingConfig from "@/lib/constants/streaming";

interface StreamingMarkdownProps {
    content: string;
    className?: string;
}

const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({ content, className }) => {
    const [displayedContent, setDisplayedContent] = useState("");

    // Use refs for mutable state to avoid re-renders during calculations
    const state = useRef({
        cursor: 0,
        speed: StreamingConfig.STREAMING_INITIAL_SPEED,
        lastArrivalTime: 0, // Initialize to 0 to detect first chunk
        avgInterval: StreamingConfig.STREAMING_INITIAL_AVG_INTERVAL,
        lastLen: 0,
    });

    const contentRef = useRef(content);

    useEffect(() => {
        contentRef.current = content;

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
                dt = Math.max(StreamingConfig.STREAMING_DT_MIN_MS, Math.min(StreamingConfig.STREAMING_DT_MAX_MS, dt));

                // Update moving average of inter-arrival time
                const alpha = dt < StreamingConfig.STREAMING_ALPHA_THRESHOLD_MS ? StreamingConfig.STREAMING_ALPHA_FAST : StreamingConfig.STREAMING_ALPHA_SLOW;
                s.avgInterval = s.avgInterval * (1 - alpha) + dt * alpha;

                s.lastArrivalTime = now;
            }

            // Calculate target speed based on clearing the TOTAL backlog over the next interval (+buffer)
            const backlog = content.length - s.cursor;
            const targetSpeed = backlog / (s.avgInterval * StreamingConfig.STREAMING_SAFETY_FACTOR);

            // Update current speed smoothly
            const momentum = targetSpeed > s.speed ? StreamingConfig.STREAMING_MOMENTUM_INCREASE : StreamingConfig.STREAMING_MOMENTUM_DECREASE;
            s.speed = s.speed * momentum + targetSpeed * (1 - momentum);

            // Hard clamps to keep it sane
            s.speed = Math.max(StreamingConfig.STREAMING_SPEED_MIN, Math.min(StreamingConfig.STREAMING_SPEED_MAX, s.speed));

            s.lastLen = content.length;
        }
    }, [content]);

    useEffect(() => {
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
    }, []); // Run animation loop once on mount

    return <MarkdownHTMLConverter className={className}>{displayedContent}</MarkdownHTMLConverter>;
};

export { StreamingMarkdown };
