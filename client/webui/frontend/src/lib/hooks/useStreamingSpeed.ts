import { useEffect, useRef } from "react";
import * as StreamingConfig from "@/lib/constants/streaming";

export interface StreamingState {
    cursor: number;
    speed: number;
    lastArrivalTime: number;
    avgInterval: number;
    lastLen: number;
}

/**
 * Hook that calculates adaptive streaming speed based on content arrival patterns.
 * Returns a ref to the streaming state that can be used by useStreamingAnimation.
 */
export function useStreamingSpeed(content: string) {
    const state = useRef<StreamingState>({
        cursor: 0,
        speed: StreamingConfig.STREAMING_INITIAL_SPEED,
        lastArrivalTime: 0,
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

            // Calculate target speed based on clearing the backlog over the next interval (+buffer)
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

    return { state, contentRef };
}
