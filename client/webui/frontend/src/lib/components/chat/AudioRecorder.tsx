import { useCallback, useRef, useState, useImperativeHandle, forwardRef } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui";
import { useSpeechToText, useAudioSettings } from "@/lib/hooks";
import { cn } from "@/lib/utils";

interface AudioRecorderProps {
    disabled?: boolean;
    onTranscriptionComplete: (text: string) => void;
    className?: string;
}

export interface AudioRecorderRef {
    startRecording: () => Promise<void>;
    stopRecording: () => Promise<void>;
    cancelRecording: () => Promise<void>;
}

export const AudioRecorder = forwardRef<AudioRecorderRef, AudioRecorderProps>(({
    disabled = false,
    onTranscriptionComplete,
    className,
}, ref) => {
    const { settings } = useAudioSettings();
    const [showError, setShowError] = useState(false);
    const existingTextRef = useRef<string>("");
    const shouldSendTranscriptionRef = useRef<boolean>(true);

    const handleTranscriptionUpdate = useCallback((text: string) => {
        // For browser STT, we get interim results
        console.log("Transcription update:", text);
    }, []);

    const handleTranscriptionComplete = useCallback(
        (text: string) => {
            // Only send transcription if not canceled
            if (shouldSendTranscriptionRef.current && text && text.trim()) {
                // Append to existing text if any
                const finalText = existingTextRef.current
                    ? `${existingTextRef.current} ${text}`.trim()
                    : text.trim();

                onTranscriptionComplete(finalText);
                existingTextRef.current = "";
            } else if (!shouldSendTranscriptionRef.current) {
                console.log("AudioRecorder: Transcription canceled, not sending");
                existingTextRef.current = "";
            }
            // Reset flag for next recording
            shouldSendTranscriptionRef.current = true;
        },
        [onTranscriptionComplete]
    );

    const handleError = useCallback((error: string) => {
        console.error("Speech-to-text error:", error);
        setShowError(true);
        // Show error longer if it's a browser support issue
        const timeout = error.includes("not supported") ? 5000 : 3000;
        setTimeout(() => setShowError(false), timeout);
    }, []);

    const { isListening, isLoading, error, startRecording, stopRecording } = useSpeechToText({
        onTranscriptionComplete: handleTranscriptionComplete,
        onTranscriptionUpdate: handleTranscriptionUpdate,
        onError: handleError,
    });

    // Expose start/stop/cancel methods via ref
    useImperativeHandle(ref, () => ({
        startRecording: async () => {
            if (!isListening) {
                existingTextRef.current = "";
                shouldSendTranscriptionRef.current = true;
                await startRecording();
            }
        },
        stopRecording: async () => {
            if (isListening) {
                shouldSendTranscriptionRef.current = true;
                await stopRecording();
            }
        },
        cancelRecording: async () => {
            if (isListening) {
                console.log("AudioRecorder: Canceling recording");
                shouldSendTranscriptionRef.current = false;
                await stopRecording();
            }
        },
    }), [isListening, startRecording, stopRecording]);

    const handleClick = useCallback(async () => {
        if (isListening) {
            shouldSendTranscriptionRef.current = true;
            await stopRecording();
        } else {
            // Store any existing text before starting recording
            existingTextRef.current = "";
            shouldSendTranscriptionRef.current = true;
            await startRecording();
        }
    }, [isListening, startRecording, stopRecording]);

    const renderIcon = () => {
        if (isLoading) {
            return <Loader2 className="size-5 animate-spin" />;
        }

        if (isListening) {
            return <MicOff className="size-5 text-red-500 animate-pulse" />;
        }

        return <Mic className="size-5" />;
    };

    const getTooltip = () => {
        if (isListening) {
            return "Stop recording";
        }
        if (isLoading) {
            return "Processing...";
        }
        if (!settings.speechToText) {
            return "Speech-to-text is disabled";
        }
        return "Start voice recording";
    };

    const getAriaLabel = () => {
        if (isListening) {
            return "Stop voice recording";
        }
        return "Start voice recording";
    };

    // Don't render if STT is disabled
    if (!settings.speechToText) {
        return null;
    }

    return (
        <div className="relative">
            <Button
                variant="ghost"
                size="icon"
                onClick={handleClick}
                disabled={disabled || isLoading}
                className={cn(
                    "transition-colors",
                    isListening && "bg-red-50 hover:bg-red-100 dark:bg-red-950 dark:hover:bg-red-900",
                    className
                )}
                tooltip={getTooltip()}
                aria-label={getAriaLabel()}
                aria-pressed={isListening}
                aria-busy={isLoading}
            >
                {renderIcon()}
            </Button>

            {/* Error indicator */}
            {showError && error && (
                <div className="absolute bottom-full right-0 mb-2 max-w-xs rounded-md bg-red-500 px-3 py-2 text-xs text-white shadow-lg">
                    <div className="font-semibold mb-1">Speech Error</div>
                    <div>{error}</div>
                    {error.includes("not supported") && (
                        <div className="mt-2 text-xs opacity-90">
                            💡 Try switching to "External API" mode in Settings
                        </div>
                    )}
                    <div className="absolute right-4 top-full border-4 border-transparent border-t-red-500" />
                </div>
            )}

            {/* Recording indicator */}
            {isListening && (
                <div className="absolute -right-1 -top-1 flex size-3 items-center justify-center">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex size-2 rounded-full bg-red-500" />
                </div>
            )}
        </div>
    );
});

AudioRecorder.displayName = "AudioRecorder";