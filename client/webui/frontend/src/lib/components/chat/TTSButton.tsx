import React, { useCallback, useMemo, useEffect, useRef, useState } from "react";
import { Volume2, VolumeX, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { useTextToSpeech, useAudioSettings, useConfigContext } from "@/lib/hooks";
import { useStreamingTTS } from "@/lib/hooks/useStreamingTTS";
import { cn } from "@/lib/utils";
import type { MessageFE, TextPart } from "@/lib/types";

interface TTSButtonProps {
    message: MessageFE;
    className?: string;
}

// Track which messages were already complete when component mounted
// This prevents auto-playing old messages when entering conversation mode
const preExistingCompleteMessages = new Set<string>();

// Global singleton to track which message is currently playing TTS
// This prevents multiple TTSButton instances from playing simultaneously
let currentlyPlayingMessageId: string | null = null;

// Extract text content from message parts
function extractTextContent(message: MessageFE): string {
    if (!message.parts || message.parts.length === 0) {
        return "";
    }

    const textParts = message.parts.filter(p => p.kind === "text") as TextPart[];
    return textParts
        .map(p => p.text)
        .join(" ")
        .trim();
}

export const TTSButton: React.FC<TTSButtonProps> = ({ message, className }) => {
    const { settings, onTTSStart, onTTSEnd } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();
    const messageId = message.metadata?.messageId || "";
    const content = useMemo(() => extractTextContent(message), [message]);
    const isStreaming = !message.isComplete;

    // Feature flag
    const ttsEnabled = configFeatureEnablement?.textToSpeech ?? true;

    // Regular TTS for complete messages
    const {
        isSpeaking: isRegularSpeaking,
        isLoading: isRegularLoading,
        speak,
        stop: stopRegular,
    } = useTextToSpeech({
        messageId,
        onStart: () => {
            onTTSStart();
        },
        onEnd: () => {
            // Clear global tracking when this message finishes
            if (currentlyPlayingMessageId === messageId) {
                currentlyPlayingMessageId = null;
            }
            onTTSEnd();
        },
        onError: error => {
            console.error("TTS error:", error);
            // Clear global tracking on error
            if (currentlyPlayingMessageId === messageId) {
                currentlyPlayingMessageId = null;
            }
            onTTSEnd();
        },
    });

    // Streaming TTS for incomplete messages
    const {
        isPlaying: isStreamingPlaying,
        isLoading: isStreamingLoading,
        processStreamingText,
        stop: stopStreaming,
    } = useStreamingTTS({
        messageId,
        onStart: () => {
            // Don't call onTTSStart here - the hook already calls it internally
        },
        onEnd: () => {
            // Clear global tracking when this message finishes
            if (currentlyPlayingMessageId === messageId) {
                currentlyPlayingMessageId = null;
            }
            // Don't call onTTSEnd here - the hook already calls it internally
        },
        onError: error => {
            console.error("Streaming TTS error:", error);
            // Clear global tracking on error
            if (currentlyPlayingMessageId === messageId) {
                currentlyPlayingMessageId = null;
            }
            // Don't call onTTSEnd here - the hook already calls it internally
        },
    });

    // Combine states
    const isSpeaking = isStreaming ? isStreamingPlaying : isRegularSpeaking;
    const isLoading = isStreaming ? isStreamingLoading : isRegularLoading;

    // Track if we've already started streaming for this message
    const hasStartedStreaming = useRef(false);
    const hasAutoPlayed = useRef(false);
    const [wasCompleteOnMount, setWasCompleteOnMount] = useState(false);

    // On mount, check if message was already complete
    useEffect(() => {
        if (message.isComplete && messageId) {
            // This message was already complete when we mounted
            setWasCompleteOnMount(true);
            preExistingCompleteMessages.add(messageId);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Only run on mount

    // Auto-play streaming TTS as content arrives
    useEffect(() => {
        // Disable automatic playback - only conversation mode (which is not implemented)
        const shouldAutoPlay = settings.conversationMode; // Removed: || settings.automaticPlayback

        if (
            shouldAutoPlay &&
            !message.isUser &&
            isStreaming &&
            content &&
            content.length > 20 && // Wait for at least some content
            !hasStartedStreaming.current
        ) {
            // Check if another message is already playing
            if (currentlyPlayingMessageId && currentlyPlayingMessageId !== messageId) {
                return;
            }
            currentlyPlayingMessageId = messageId;

            hasStartedStreaming.current = true;
            processStreamingText(content, false);
        } else if (shouldAutoPlay && !message.isUser && isStreaming && hasStartedStreaming.current) {
            // Continue processing as more content arrives
            processStreamingText(content, false);
        } else if (shouldAutoPlay && !message.isUser && message.isComplete && hasStartedStreaming.current && !hasAutoPlayed.current) {
            // Finalize streaming when message completes - process ALL remaining content
            hasAutoPlayed.current = true;
            // Mark as complete so all remaining text is processed
            processStreamingText(content, true);
        } else if (shouldAutoPlay && !message.isUser && message.isComplete && !hasStartedStreaming.current && !hasAutoPlayed.current && content && !wasCompleteOnMount) {
            // Message completed before we started streaming (very short message or fast completion)
            // Start and immediately finalize
            // Check if another message is already playing
            if (currentlyPlayingMessageId && currentlyPlayingMessageId !== messageId) {
                return;
            }
            currentlyPlayingMessageId = messageId;
            hasStartedStreaming.current = true;
            hasAutoPlayed.current = true;
            processStreamingText(content, true);
        }
    }, [settings.conversationMode, settings.automaticPlayback, message.isUser, isStreaming, message.isComplete, content, messageId, processStreamingText, wasCompleteOnMount]);

    // Auto-play for complete messages (fallback if streaming wasn't used)
    // BUT only if the message wasn't already complete when we mounted
    useEffect(() => {
        // Disable automatic playback - only conversation mode (which is not implemented)
        const shouldAutoPlay = settings.conversationMode; // Removed: || settings.automaticPlayback

        if (
            shouldAutoPlay &&
            !message.isUser &&
            message.isComplete &&
            content &&
            !isSpeaking &&
            !isLoading &&
            !hasAutoPlayed.current &&
            !hasStartedStreaming.current &&
            !wasCompleteOnMount // NEW: Don't auto-play if message was already complete on mount
        ) {
            // Check if another message is already playing
            if (currentlyPlayingMessageId && currentlyPlayingMessageId !== messageId) {
                return;
            }
            currentlyPlayingMessageId = messageId;

            hasAutoPlayed.current = true;

            // Small delay to ensure audio context is ready, but keep it minimal
            const timer = setTimeout(() => {
                speak(content);
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [settings.conversationMode, settings.automaticPlayback, message.isUser, message.isComplete, content, isSpeaking, isLoading, messageId, speak, wasCompleteOnMount]);

    // Reset flags when message changes
    useEffect(() => {
        hasAutoPlayed.current = false;
        hasStartedStreaming.current = false;
        // Check if the new message is already complete
        if (message.isComplete && messageId) {
            setWasCompleteOnMount(true);
            preExistingCompleteMessages.add(messageId);
        } else {
            setWasCompleteOnMount(false);
        }
    }, [messageId, message.isComplete]);

    const handleClick = useCallback(async () => {
        if (isSpeaking) {
            if (isStreaming) {
                stopStreaming();
            } else {
                stopRegular();
            }
        } else if (content) {
            if (isStreaming) {
                hasStartedStreaming.current = true;
                await processStreamingText(content, false);
            } else {
                await speak(content);
            }
        }
    }, [isSpeaking, isStreaming, content, speak, stopRegular, stopStreaming, processStreamingText]);

    const renderIcon = () => {
        if (isLoading) {
            return <Loader2 className="size-4 animate-spin" />;
        }

        if (isSpeaking) {
            return <VolumeX className="size-4" />;
        }

        return <Volume2 className="size-4" />;
    };

    const getTooltip = () => {
        if (isSpeaking) {
            return "Stop reading";
        }
        if (isLoading) {
            return "Generating audio...";
        }
        if (!settings.textToSpeech) {
            return "Text-to-speech is disabled";
        }
        return "Read aloud";
    };

    // Don't render if TTS feature is disabled, TTS setting is disabled, or has no content
    if (!ttsEnabled || !settings.textToSpeech || !content) {
        return null;
    }

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={handleClick}
            disabled={isLoading || !content}
            className={cn("size-8 transition-colors", isSpeaking && "bg-blue-50 hover:bg-blue-100 dark:bg-blue-950 dark:hover:bg-blue-900", className)}
            tooltip={getTooltip()}
            aria-label={isSpeaking ? "Stop reading aloud" : "Read aloud"}
            aria-pressed={isSpeaking}
            aria-busy={isLoading}
        >
            {renderIcon()}
        </Button>
    );
};
