import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Copy, Check } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { cn } from "@/lib/utils";
import { useChatContext, useConfigContext } from "@/lib/hooks";
import type { MessageFE, TextPart } from "@/lib/types";
import { TTSButton } from "./TTSButton";
import { extractDisplayTextFromHTML } from "@/lib/utils/mentionUtils";

interface MessageHoverButtonsProps {
    message: MessageFE;
    className?: string;
    /** Optional text content override */
    textContentOverride?: string;
}

export const MessageHoverButtons: React.FC<MessageHoverButtonsProps> = ({ message, className, textContentOverride }) => {
    const { addNotification } = useChatContext();
    const { configFeatureEnablement } = useConfigContext();
    const mentionsEnabled = configFeatureEnablement?.mentions ?? false;
    const [isCopied, setIsCopied] = useState(false);
    const buttonRef = useRef<HTMLButtonElement>(null);

    // Extract text content from message parts, or use override if provided
    const getTextContent = useCallback((): string => {
        if (textContentOverride) {
            return textContentOverride;
        }
        // For user messages with displayHtml (containing mention chips), extract display text
        if (message.isUser && message.displayHtml) {
            return extractDisplayTextFromHTML(message.displayHtml);
        }

        // For other messages, use parts
        if (!message.parts || message.parts.length === 0) {
            return "";
        }
        const textParts = message.parts.filter(p => p.kind === "text") as TextPart[];
        return textParts.map(p => p.text).join("");
    }, [textContentOverride, message.isUser, message.displayHtml, message.parts]);

    // Copy functionality
    const handleCopy = useCallback(() => {
        const text = getTextContent();
        if (text.trim()) {
            // For user messages with displayHtml, copy both HTML and plain text (only if mentions enabled)
            if (message.isUser && message.displayHtml && mentionsEnabled) {
                const clipboardItem = new ClipboardItem({
                    "text/html": new Blob([message.displayHtml], { type: "text/html" }),
                    "text/plain": new Blob([text.trim()], { type: "text/plain" }),
                });

                navigator.clipboard
                    .write([clipboardItem])
                    .then(() => {
                        setIsCopied(true);
                        addNotification("Message copied to clipboard!", "success");
                    })
                    .catch(err => {
                        // Not displaying error to user, dialog is too aggressive for clipboard failures
                        console.error("Failed to copy text:", err);
                    });
            } else {
                // For other messages, just copy plain text
                navigator.clipboard
                    .writeText(text.trim())
                    .then(() => {
                        setIsCopied(true);
                        addNotification("Message copied to clipboard!", "success");
                    })
                    .catch(err => {
                        // Not displaying error to user, dialog is too aggressive for clipboard failures
                        console.error("Failed to copy text:", err);
                    });
            }
        } else {
            addNotification("No text content to copy", "info");
        }
    }, [getTextContent, addNotification, message.isUser, message.displayHtml, mentionsEnabled]);

    // Reset copied state after 2 seconds
    useEffect(() => {
        if (isCopied) {
            const timer = setTimeout(() => setIsCopied(false), 2000);
            return () => clearTimeout(timer);
        }
    }, [isCopied]);

    // Add keyboard shortcut for copy (Ctrl+Shift+C)
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            // Check for Ctrl+Shift+C
            if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "c") {
                event.preventDefault();
                handleCopy();

                // Flash the button to provide visual feedback
                if (buttonRef.current) {
                    buttonRef.current.classList.add("bg-[var(--color-secondary-w20)]", "dark:bg-[var(--color-secondary-w80)]");
                    setTimeout(() => {
                        buttonRef.current?.classList.remove("bg-[var(--color-secondary-w20)]", "dark:bg-[var(--color-secondary-w80)]");
                    }, 200);
                }
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [handleCopy]);

    // Create a synthetic message with text content override
    const messageForTTS = useMemo((): MessageFE => {
        if (!textContentOverride) {
            return message;
        }
        return {
            ...message,
            parts: [{ kind: "text", text: textContentOverride }],
        };
    }, [message, textContentOverride]);

    // Don't show buttons for status messages
    if (message.isStatusBubble || message.isStatusMessage) {
        return null;
    }

    return (
        <div className={cn("flex justify-start gap-1 text-gray-500", className)}>
            {/* TTS Button - for AI messages */}
            {!message.isUser && <TTSButton message={messageForTTS} />}

            {/* Copy button - all messages */}
            <Button ref={buttonRef} variant="ghost" size="icon" className="h-8 w-8" onClick={handleCopy} tooltip={isCopied ? "Copied!" : "Copy to clipboard"}>
                {isCopied ? <Check className="h-4 w-4 text-[var(--color-success-wMain)]" /> : <Copy className="h-4 w-4" />}
            </Button>
        </div>
    );
};
