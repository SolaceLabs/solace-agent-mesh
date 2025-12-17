import { useState, useRef, useCallback, useEffect } from "react";
import { useAudioSettings } from "./useAudioSettings";
import { api } from "@/lib/api";

interface UseStreamingTTSOptions {
    messageId: string;
    onStart?: () => void;
    onEnd?: () => void;
    onError?: (error: string) => void;
}

interface UseStreamingTTSReturn {
    isPlaying: boolean;
    isLoading: boolean;
    error: string | null;
    processStreamingText: (text: string, isComplete: boolean) => Promise<void>;
    stop: () => void;
}

interface AudioQueueItem {
    audio: HTMLAudioElement;
    sentence: string;
    index: number; // Track original order
}

/**
 * Hook for streaming TTS - generates and plays audio sentence-by-sentence
 * as text streams in, reducing perceived latency significantly.
 */
export function useStreamingTTS(options: UseStreamingTTSOptions): UseStreamingTTSReturn {
    const { messageId, onStart, onEnd, onError } = options;
    const { settings, onTTSStart, onTTSEnd } = useAudioSettings();

    const [isPlaying, setIsPlaying] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Track processed sentences by content hash to avoid duplicates while maintaining order
    const processedSentencesRef = useRef<Set<string>>(new Set());
    const audioQueueRef = useRef<AudioQueueItem[]>([]);
    const isPlayingQueueRef = useRef(false);
    const currentAudioRef = useRef<HTMLAudioElement | null>(null);
    const lastTextRef = useRef<string>("");
    const lastTextLengthRef = useRef<number>(0);
    const isStoppedRef = useRef(false); // Track if we've been explicitly stopped
    const hasNotifiedStartRef = useRef(false); // Track if we've notified global state
    const isGeneratingRef = useRef(false); // Track if we're still generating audio
    const processingPromiseRef = useRef<Promise<void> | null>(null); // Track ongoing processing
    const pendingTextRef = useRef<{ text: string; isComplete: boolean } | null>(null); // Track pending update

    // Store callbacks in refs to avoid recreating processStreamingText
    const onStartRef = useRef(onStart);
    const onEndRef = useRef(onEnd);
    const onErrorRef = useRef(onError);
    const onTTSStartRef = useRef(onTTSStart);
    const onTTSEndRef = useRef(onTTSEnd);

    useEffect(() => {
        onStartRef.current = onStart;
        onEndRef.current = onEnd;
        onErrorRef.current = onError;
        onTTSStartRef.current = onTTSStart;
        onTTSEndRef.current = onTTSEnd;
    }, [onStart, onEnd, onError, onTTSStart, onTTSEnd]);

    /**
     * Extract complete sentences from text
     * Returns sentences in order they appear
     */
    const extractSentences = useCallback((text: string): string[] => {
        // Match sentences ending with punctuation
        const sentenceRegex = /[^.!?]+[.!?]+(?:\s|$)/g;
        const sentences = text.match(sentenceRegex) || [];
        return sentences.map(s => s.trim()).filter(s => s.length > 0);
    }, []);

    /**
     * Generate TTS audio using streaming endpoint for much faster performance
     * The backend chunks and streams audio, we collect it all and play as one piece
     */
    const generateStreamedAudio = useCallback(
        async (text: string): Promise<HTMLAudioElement | null> => {
            try {
                console.log(`[StreamingTTS] Requesting streaming TTS for text length: ${text.length}`);

                const response = await api.webui.post(
                    "/api/v1/speech/tts/stream",
                    {
                        input: text,
                        voice: settings.voice,
                        runId: messageId,
                    },
                    { fullResponse: true }
                );

                if (!response.ok) {
                    throw new Error(`TTS streaming failed: ${response.statusText}`);
                }

                // Read the entire streaming response
                const reader = response.body?.getReader();
                if (!reader) {
                    throw new Error("No response body reader available");
                }

                const chunks: Uint8Array[] = [];
                let totalSize = 0;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    if (value) {
                        chunks.push(value);
                        totalSize += value.length;
                    }
                }

                console.log(`[StreamingTTS] Received ${chunks.length} chunks, total size: ${totalSize} bytes`);

                // Combine all chunks into a single blob
                const combinedArray = new Uint8Array(totalSize);
                let offset = 0;
                for (const chunk of chunks) {
                    combinedArray.set(chunk, offset);
                    offset += chunk.length;
                }

                // Create audio from combined data
                const audioBlob = new Blob([combinedArray], { type: "audio/mpeg" });
                console.log(`[StreamingTTS] Created audio blob: size=${audioBlob.size}, type=${audioBlob.type}`);

                if (audioBlob.size === 0) {
                    throw new Error("Received empty audio stream");
                }

                const blobUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio();

                audio.onerror = e => {
                    const error = audio.error;
                    console.error(`[StreamingTTS] Audio error: code=${error?.code}, message=${error?.message}`, e);
                };

                audio.src = blobUrl;
                audio.playbackRate = settings.playbackRate || 1.0;
                audio.load();

                return audio;
            } catch (err) {
                console.error("[StreamingTTS] Error generating streamed audio:", err);
                return null;
            }
        },
        [settings.voice, settings.playbackRate, messageId]
    );

    /**
     * Play next audio in queue
     */
    const playNextInQueue = useCallback(() => {
        // Don't play if we've been stopped
        if (isStoppedRef.current) {
            console.log("[StreamingTTS] Skipping playback - stopped");
            return;
        }

        if (isPlayingQueueRef.current || audioQueueRef.current.length === 0) {
            return;
        }

        isPlayingQueueRef.current = true;
        const item = audioQueueRef.current.shift();

        if (!item) {
            isPlayingQueueRef.current = false;
            return;
        }

        const { audio, sentence } = item;
        currentAudioRef.current = audio;

        console.log(`[StreamingTTS] Playing sentence: "${sentence.substring(0, 50)}..."`);

        audio.onplay = () => {
            console.log("[StreamingTTS] Audio onplay event fired");
            setIsPlaying(true);
            setIsLoading(false);
            if (!hasNotifiedStartRef.current) {
                // First audio starting - notify global state
                console.log("[StreamingTTS] First audio playing, notifying global state");
                hasNotifiedStartRef.current = true;
                onStartRef.current?.();
                if (onTTSStartRef.current) {
                    onTTSStartRef.current();
                }
            }
        };

        audio.onended = () => {
            console.log("[StreamingTTS] Audio onended event fired");
            URL.revokeObjectURL(audio.src);
            currentAudioRef.current = null;
            isPlayingQueueRef.current = false;

            // Play next in queue
            if (audioQueueRef.current.length > 0) {
                console.log("[StreamingTTS] More audio in queue, playing next");
                playNextInQueue();
            } else if (!isGeneratingRef.current) {
                // Queue empty AND not generating more - we're truly done
                console.log("[StreamingTTS] All audio played and generation complete, notifying global state");
                setIsPlaying(false);
                onEndRef.current?.();
                if (onTTSEndRef.current) {
                    onTTSEndRef.current();
                }
            } else {
                // Queue empty but still generating - poll until generation completes
                console.log("[StreamingTTS] Queue empty but still generating, polling...");
                let pollCount = 0;
                const maxPolls = 100; // 10 seconds max
                const checkInterval = setInterval(() => {
                    pollCount++;
                    if (audioQueueRef.current.length > 0) {
                        console.log("[StreamingTTS] New audio arrived during poll, playing");
                        clearInterval(checkInterval);
                        playNextInQueue();
                    } else if (!isGeneratingRef.current && !isPlayingQueueRef.current) {
                        // Generation finished AND not playing
                        console.log("[StreamingTTS] Generation finished and not playing, notifying global state");
                        clearInterval(checkInterval);
                        setIsPlaying(false);
                        onEndRef.current?.();
                        if (onTTSEndRef.current) {
                            onTTSEndRef.current();
                        }
                    } else if (pollCount >= maxPolls) {
                        // Safety timeout - force end after 10 seconds
                        console.log("[StreamingTTS] Poll timeout after 10s, forcing end");
                        clearInterval(checkInterval);
                        isGeneratingRef.current = false;
                        setIsPlaying(false);
                        onEndRef.current?.();
                        if (onTTSEndRef.current) {
                            onTTSEndRef.current();
                        }
                    }
                    // Keep polling while generating OR playing
                }, 100);
            }
        };

        audio.onerror = () => {
            // MediaError codes: 1=ABORTED, 2=NETWORK, 3=DECODE, 4=SRC_NOT_SUPPORTED
            const errorCode = audio.error?.code;
            if (errorCode === 1) {
                // MEDIA_ERR_ABORTED - expected when stopping
                console.log("[StreamingTTS] Ignoring ABORTED error (expected during stop)");
                return;
            }

            const errorMsg = `Failed to play audio (code: ${errorCode})`;
            setError(errorMsg);
            onErrorRef.current?.(errorMsg);
            URL.revokeObjectURL(audio.src);
            currentAudioRef.current = null;
            isPlayingQueueRef.current = false;

            // Try next in queue
            if (audioQueueRef.current.length > 0) {
                playNextInQueue();
            } else {
                setIsPlaying(false);
                onEnd?.();
                onTTSEnd();
            }
        };

        audio.play().catch(err => {
            // Ignore AbortError - it's expected when stopping
            if (err.name === "AbortError") {
                console.log("[StreamingTTS] Ignoring AbortError from play() (expected during stop)");
                return;
            }
            console.error("[StreamingTTS] Error playing audio:", err);
            isPlayingQueueRef.current = false;
            playNextInQueue();
        });
    }, [onEnd, onTTSEnd]);

    /**
     * Internal processing function using streaming endpoint for much faster performance
     * Processes text as it arrives and generates audio using backend streaming
     */
    const doProcessing = useCallback(
        async (text: string, isComplete: boolean) => {
            console.log(`[StreamingTTS] doProcessing called: textLen=${text.length}, isComplete=${isComplete}`);

            if (isStoppedRef.current) {
                console.log("[StreamingTTS] Skipping - stopped");
                return;
            }

            // Only process when we have new complete sentences or message is complete
            const sentences = extractSentences(text);
            const newText = sentences.join(" ");

            // Add remaining text if message is complete
            if (isComplete) {
                const lastSentence = sentences[sentences.length - 1] || "";
                const lastSentenceEnd = text.lastIndexOf(lastSentence) + lastSentence.length;
                const remainingText = text.substring(lastSentenceEnd).trim();
                if (remainingText) {
                    console.log(`[StreamingTTS] Adding remaining text: "${remainingText.substring(0, 50)}..."`);
                }
            }

            // Skip if we've already processed this text
            const textToProcess = isComplete ? text : newText;
            if (processedSentencesRef.current.has(textToProcess) || textToProcess.length < 10) {
                console.log("[StreamingTTS] Skipping - already processed or too short");
                return;
            }

            // Mark as processed
            processedSentencesRef.current.add(textToProcess);
            lastTextRef.current = text;
            lastTextLengthRef.current = text.length;

            console.log(`[StreamingTTS] Processing text (${textToProcess.length} chars)`);

            setIsLoading(true);
            isStoppedRef.current = false;
            isGeneratingRef.current = true;

            try {
                // Use streaming endpoint - much faster!
                const audio = await generateStreamedAudio(textToProcess);

                if (audio && !isStoppedRef.current) {
                    audioQueueRef.current.push({
                        audio,
                        sentence: textToProcess.substring(0, 50),
                        index: audioQueueRef.current.length,
                    });

                    console.log(`[StreamingTTS] Added audio to queue (size: ${audioQueueRef.current.length})`);

                    // Start playing if not already playing
                    if (!isPlayingQueueRef.current) {
                        console.log("[StreamingTTS] Starting playback");
                        playNextInQueue();
                    }
                }
            } catch (err) {
                console.error("[StreamingTTS] Error processing:", err);
            }

            setIsLoading(false);

            if (isComplete) {
                isGeneratingRef.current = false;
                console.log(`[StreamingTTS] Message complete`);
            }
        },
        [extractSentences, generateStreamedAudio, playNextInQueue]
    );

    /**
     * Process streaming text and generate TTS for new sentences
     * Ensures only one processing operation at a time
     */
    const processStreamingText = useCallback(
        async (text: string, isComplete: boolean) => {
            // If already processing, queue this update
            if (processingPromiseRef.current) {
                console.log("[StreamingTTS] Already processing, queuing update");
                pendingTextRef.current = { text, isComplete };
                return;
            }

            // Start processing
            processingPromiseRef.current = doProcessing(text, isComplete);

            try {
                await processingPromiseRef.current;
            } finally {
                processingPromiseRef.current = null;

                // Process any pending update
                if (pendingTextRef.current) {
                    const pending = pendingTextRef.current;
                    pendingTextRef.current = null;
                    console.log("[StreamingTTS] Processing queued update");
                    await processStreamingText(pending.text, pending.isComplete);
                }
            }
        },
        [doProcessing]
    );

    /**
     * Stop playback and clear queue
     */
    const stop = useCallback(() => {
        // Only stop if we're actually playing
        if (!isPlayingQueueRef.current && audioQueueRef.current.length === 0) {
            return; // Silently ignore if nothing playing
        }

        console.log("[StreamingTTS] Stopping playback");
        isStoppedRef.current = true; // Mark as stopped

        // Stop current audio
        if (currentAudioRef.current) {
            try {
                currentAudioRef.current.pause();
                currentAudioRef.current.currentTime = 0;
                URL.revokeObjectURL(currentAudioRef.current.src);
            } catch {
                // Ignore errors during cleanup
            }
            currentAudioRef.current = null;
        }

        // Clear queue
        audioQueueRef.current.forEach(item => {
            try {
                URL.revokeObjectURL(item.audio.src);
            } catch {
                // Ignore errors during cleanup
            }
        });
        audioQueueRef.current = [];

        isPlayingQueueRef.current = false;
        setIsPlaying(false);
        setIsLoading(false);

        // Only notify if we were actually playing
        if (isPlaying) {
            onEnd?.();
            onTTSEnd();
        }
    }, [isPlaying, onEnd, onTTSEnd]);

    /**
     * Reset when message changes
     */
    useEffect(() => {
        // Capture current value at the start of the effect
        const processedSentences = processedSentencesRef.current;

        // Clear state when message changes
        processedSentences.clear();
        lastTextRef.current = "";
        lastTextLengthRef.current = 0;
        isStoppedRef.current = false; // Reset stopped flag for new message
        hasNotifiedStartRef.current = false; // Reset notification flag
        isGeneratingRef.current = false; // Reset generating flag
        processingPromiseRef.current = null; // Reset processing promise
        pendingTextRef.current = null; // Clear any pending updates

        return () => {
            // Capture current value for cleanup
            const processedSentences = processedSentencesRef.current;

            // Cleanup on unmount only if actually playing
            if (isPlayingQueueRef.current || audioQueueRef.current.length > 0) {
                console.log("[StreamingTTS] Cleanup: stopping playback for message change/unmount");
                isStoppedRef.current = true;

                // Stop current audio
                if (currentAudioRef.current) {
                    try {
                        currentAudioRef.current.pause();
                        URL.revokeObjectURL(currentAudioRef.current.src);
                    } catch {
                        // Ignore
                    }
                    currentAudioRef.current = null;
                }

                // Clear queue
                audioQueueRef.current.forEach(item => {
                    try {
                        URL.revokeObjectURL(item.audio.src);
                    } catch {
                        // Ignore
                    }
                });
                audioQueueRef.current = [];
                isPlayingQueueRef.current = false;
            }
            processedSentences.clear();
            lastTextRef.current = "";
            lastTextLengthRef.current = 0;
            processingPromiseRef.current = null;
            pendingTextRef.current = null;
        };
    }, [messageId]); // Only messageId - no stop dependency!

    return {
        isPlaying,
        isLoading,
        error,
        processStreamingText,
        stop,
    };
}
