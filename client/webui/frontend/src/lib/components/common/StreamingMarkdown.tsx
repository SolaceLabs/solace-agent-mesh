import React, { useState, useEffect, useRef } from "react";
import { MarkdownHTMLConverter } from "./MarkdownHTMLConverter";

interface StreamingMarkdownProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
}

export const StreamingMarkdown: React.FC<StreamingMarkdownProps> = ({ content, isStreaming, className }) => {
    // If not streaming initially, just show content. If streaming, start empty (or handle resume if needed).
    // We trust that if isStreaming is true, it's a new message or we want the effect.
    // However, for existing messages that re-render, we don't want to restart animation.
    // Since this component is likely remounted or reused, we need to be careful.
    // But in the ChatPage list, keys are messageIds, so they are stable.
    // A new message starts with content="", isStreaming=true.
    
    const [displayedContent, setDisplayedContent] = useState(isStreaming ? "" : content);
    const contentRef = useRef(content);

    useEffect(() => {
        contentRef.current = content;
    }, [content]);

    useEffect(() => {
        if (!isStreaming) {
            setDisplayedContent(content);
            return;
        }

        let animationFrameId: number;
        let lastTime = Date.now();
        const interval = 20; // ms between updates, ~50fps effectively but controlled speed

        const animate = () => {
            const now = Date.now();
            if (now - lastTime >= interval) {
                setDisplayedContent(prev => {
                    const target = contentRef.current;
                    
                    // Case 1: Target is shorter or different (correction/reset)
                    if (prev.length > target.length || !target.startsWith(prev)) {
                        return target;
                    }

                    // Case 2: Caught up
                    if (prev.length === target.length) {
                        return prev;
                    }

                    // Case 3: Need to append
                    const remaining = target.length - prev.length;
                    // Dynamic chunk size: fast catchup if behind, slow typing if close
                    // If we just got a huge chunk (e.g. 100 chars), we want to show it relatively quickly but smoothly.
                    // Say we want to process 100 chars in 500ms? That's 0.2 chars/ms.
                    // With 20ms interval, that's 4 chars per tick.
                    // Let's use a smoother approach: always type at least 1 char.
                    // If remaining is large, take a fraction.
                    const chunkSize = Math.max(1, Math.min(10, Math.ceil(remaining / 5)));
                    
                    return target.slice(0, prev.length + chunkSize);
                });
                lastTime = now;
            }
            animationFrameId = requestAnimationFrame(animate);
        };

        animationFrameId = requestAnimationFrame(animate);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isStreaming]); // Dependency on content removed to prevent restarting animation loop on every chunk

    return <MarkdownHTMLConverter className={className}>{displayedContent}</MarkdownHTMLConverter>;
};
