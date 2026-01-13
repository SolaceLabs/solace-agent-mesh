import { useState, useRef, useCallback, useEffect } from "react";
import { useAudioSettings } from "./useAudioSettings";
import { api } from "@/lib/api";

interface UseTextToSpeechOptions {
    messageId?: string;
    onStart?: () => void;
    onEnd?: () => void;
    onError?: (error: string) => void;
}

interface UseTextToSpeechReturn {
    isSpeaking: boolean;
    isLoading: boolean;
    error: string | null;
    voices: VoiceOption[];
    speak: (text: string) => Promise<void>;
    stop: () => void;
    pause: () => void;
    resume: () => void;
}

export interface VoiceOption {
    value: string;
    label: string;
}

export function useTextToSpeech(options: UseTextToSpeechOptions = {}): UseTextToSpeechReturn {
    const { messageId, onStart, onEnd, onError } = options;
    const { settings } = useAudioSettings();

    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [voices, setVoices] = useState<VoiceOption[]>([]);

    // Browser TTS refs
    const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

    // External TTS refs
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const audioUrlRef = useRef<string | null>(null);

    // Chunk-by-chunk playback refs
    const audioQueueRef = useRef<HTMLAudioElement[]>([]);
    const isPlayingQueueRef = useRef(false);
    const currentAudioIndexRef = useRef(0);
    const streamDoneRef = useRef(false); // Track if stream has finished

    const isBrowserMode = settings.engineTTS === "browser";

    // Load browser voices
    useEffect(() => {
        if (!isBrowserMode) return;

        const loadVoices = () => {
            const synth = window.speechSynthesis;
            if (!synth) return;

            const availableVoices = synth.getVoices();
            const voiceOptions: VoiceOption[] = availableVoices
                .filter(voice => {
                    // Filter based on cloudBrowserVoices setting
                    if (settings.cloudBrowserVoices) {
                        return true; // Include all voices
                    }
                    return voice.localService; // Only local voices
                })
                .map(voice => ({
                    value: voice.name,
                    label: `${voice.name} (${voice.lang})`,
                }));

            setVoices(voiceOptions);
        };

        loadVoices();

        // Chrome loads voices asynchronously
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = loadVoices;
        }

        return () => {
            if (window.speechSynthesis.onvoiceschanged) {
                window.speechSynthesis.onvoiceschanged = null;
            }
        };
    }, [isBrowserMode, settings.cloudBrowserVoices]);

    // Load external voices
    useEffect(() => {
        if (isBrowserMode) return;

        const loadExternalVoices = async () => {
            try {
                // Include provider in query to get provider-specific voices
                const provider = settings.ttsProvider || "gemini";
                const data = await api.webui.get(`/api/v1/speech/voices?provider=${provider}`);
                const voiceOptions: VoiceOption[] = (data.voices || []).map((voice: string) => ({
                    value: voice,
                    label: voice,
                }));
                setVoices(voiceOptions);
            } catch (err) {
                console.error("Failed to load external voices:", err);
            }
        };

        loadExternalVoices();
    }, [isBrowserMode, settings.ttsProvider]); // Re-load when provider changes

    // Cleanup function
    const cleanup = useCallback(() => {
        if (utteranceRef.current) {
            window.speechSynthesis.cancel();
            utteranceRef.current = null;
        }

        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.src = "";
            audioRef.current = null;
        }

        if (audioUrlRef.current) {
            URL.revokeObjectURL(audioUrlRef.current);
            audioUrlRef.current = null;
        }

        // Cleanup audio queue
        audioQueueRef.current.forEach(audio => {
            audio.pause();
            if (audio.src) {
                URL.revokeObjectURL(audio.src);
            }
        });
        audioQueueRef.current = [];
        isPlayingQueueRef.current = false;
        currentAudioIndexRef.current = 0;
        streamDoneRef.current = false;
    }, []);

    // Browser TTS implementation
    const speakBrowser = useCallback(
        async (text: string) => {
            const synth = window.speechSynthesis;

            if (!synth) {
                const errorMsg = "Speech synthesis is not supported in this browser";
                setError(errorMsg);
                onError?.(errorMsg);
                return;
            }

            try {
                // Cancel any ongoing speech
                synth.cancel();

                // Preprocess markdown for natural speech using the backend endpoint.
                let processedText = text;
                try {
                    const response = await api.webui.post("/api/v1/speech/preprocess", {
                        text,
                        read_code_blocks: false,
                        read_images: true,
                        read_citations: true,
                    });
                    processedText = response.text || text;
                } catch (preprocessError) {
                    // If preprocessing fails, fall back to using the original text
                    console.warn("[TTS] Markdown preprocessing failed, using original text:", preprocessError);
                }

                const utterance = new SpeechSynthesisUtterance(processedText);
                utterance.rate = settings.playbackRate || 1.0;
                utterance.lang = settings.languageSTT || "en-US";

                // Set voice if specified
                if (settings.voice) {
                    const availableVoices = synth.getVoices();
                    const selectedVoice = availableVoices.find(v => v.name === settings.voice);
                    if (selectedVoice) {
                        utterance.voice = selectedVoice;
                    }
                }

                utterance.onstart = () => {
                    setIsSpeaking(true);
                    setError(null);
                    onStart?.();
                };

                utterance.onend = () => {
                    setIsSpeaking(false);
                    utteranceRef.current = null;
                    onEnd?.();
                };

                utterance.onerror = event => {
                    const errorMsg = `Speech synthesis error: ${event.error}`;
                    setError(errorMsg);
                    onError?.(errorMsg);
                    setIsSpeaking(false);
                    utteranceRef.current = null;
                };

                utteranceRef.current = utterance;
                synth.speak(utterance);
            } catch (err) {
                const errorMsg = `Failed to speak: ${err}`;
                setError(errorMsg);
                onError?.(errorMsg);
            }
        },
        [settings.playbackRate, settings.languageSTT, settings.voice, onStart, onEnd, onError]
    );

    // Play next audio in queue - ensures sequential playback
    const playNextInQueue = useCallback(() => {
        if (!isPlayingQueueRef.current) {
            return;
        }

        // Check if we have more chunks to play
        if (currentAudioIndexRef.current >= audioQueueRef.current.length) {
            // No more chunks available yet
            if (streamDoneRef.current) {
                // Stream is done and we've played all chunks - finish
                setIsSpeaking(false);
                isPlayingQueueRef.current = false;
                currentAudioIndexRef.current = 0;

                // Cleanup all audio elements
                audioQueueRef.current.forEach(audio => {
                    if (audio.src) {
                        URL.revokeObjectURL(audio.src);
                    }
                });
                audioQueueRef.current = [];
                streamDoneRef.current = false;
                onEnd?.();
            } else {
                // Stream still in progress - wait for more chunks
                // Use a short timeout to check again
                setTimeout(() => {
                    playNextInQueue();
                }, 100);
            }
            return;
        }

        const chunkIndex = currentAudioIndexRef.current;
        const audio = audioQueueRef.current[chunkIndex];

        // Increment index BEFORE playing to prevent race conditions
        currentAudioIndexRef.current++;

        audio.onended = () => {
            playNextInQueue();
        };

        audio.onerror = () => {
            playNextInQueue(); // Try next chunk
        };

        audio.play().catch(err => {
            console.error(`[TTS] Failed to play chunk ${chunkIndex + 1}:`, err);
            playNextInQueue(); // Try next chunk
        });
    }, [onEnd]);

    // External TTS implementation - play chunks as they arrive
    const speakExternal = useCallback(
        async (text: string) => {
            // Stop any existing audio first
            cleanup();

            setIsLoading(true);

            try {
                // Check cache first if enabled
                if (settings.cacheTTS) {
                    const cache = await caches.open("tts-responses");
                    const cacheKey = `${text}-${settings.voice}-${settings.ttsProvider || "default"}`;
                    const cachedResponse = await cache.match(cacheKey);

                    if (cachedResponse) {
                        const audioBlob = await cachedResponse.blob();
                        const blobUrl = URL.createObjectURL(audioBlob);

                        const audio = new Audio(blobUrl);
                        audio.playbackRate = settings.playbackRate || 1.0;

                        audio.onplay = () => {
                            setIsSpeaking(true);
                            setIsLoading(false);
                            setError(null);
                            onStart?.();
                        };

                        audio.onended = () => {
                            setIsSpeaking(false);
                            URL.revokeObjectURL(blobUrl);
                            audioRef.current = null;
                            onEnd?.();
                        };

                        audio.onerror = () => {
                            const errorMsg = "Failed to play cached audio";
                            setError(errorMsg);
                            onError?.(errorMsg);
                            setIsSpeaking(false);
                            setIsLoading(false);
                            URL.revokeObjectURL(blobUrl);
                        };

                        audioRef.current = audio;
                        audioUrlRef.current = blobUrl;
                        await audio.play();
                        return;
                    }
                }

                // Use streaming endpoint - play chunks as they arrive
                const response = await api.webui.post(
                    "/api/v1/speech/tts/stream",
                    {
                        input: text,
                        voice: settings.voice,
                        runId: messageId || `tts-${Date.now()}`,
                        provider: settings.ttsProvider,
                    },
                    { fullResponse: true }
                );

                if (!response.ok) {
                    throw new Error(`TTS request failed: ${response.statusText}`);
                }

                const reader = response.body?.getReader();
                if (!reader) {
                    throw new Error("No response body reader available");
                }

                let firstChunkPlayed = false;
                const allChunks: Uint8Array[] = []; // For caching

                // Reset queue state - CRITICAL for order preservation
                audioQueueRef.current = [];
                currentAudioIndexRef.current = 0;
                isPlayingQueueRef.current = true;
                streamDoneRef.current = false; // Reset stream done flag

                while (true) {
                    const { done, value } = await reader.read();

                    if (done) {
                        // Mark stream as complete so playNextInQueue knows when to finish
                        streamDoneRef.current = true;

                        // Cache the complete audio if enabled
                        if (settings.cacheTTS && allChunks.length > 0) {
                            const totalSize = allChunks.reduce((sum, chunk) => sum + chunk.length, 0);
                            const combinedArray = new Uint8Array(totalSize);
                            let offset = 0;
                            for (const chunk of allChunks) {
                                combinedArray.set(chunk, offset);
                                offset += chunk.length;
                            }

                            const audioBlob = new Blob([combinedArray], { type: "audio/mpeg" });
                            const cache = await caches.open("tts-responses");
                            const cacheKey = `${text}-${settings.voice}-${settings.ttsProvider || "default"}`;

                            const responseToCache = new Response(audioBlob, {
                                headers: {
                                    "Content-Type": "audio/mpeg",
                                    "Content-Length": audioBlob.size.toString(),
                                },
                            });

                            await cache.put(cacheKey, responseToCache);
                        }
                        break;
                    }

                    if (value && value.length > 0) {
                        // Store for caching (preserves order in array)
                        allChunks.push(value);

                        // Create audio element for this chunk
                        const chunkBlob = new Blob([value], { type: "audio/mpeg" });
                        const blobUrl = URL.createObjectURL(chunkBlob);
                        const audio = new Audio(blobUrl);
                        audio.playbackRate = settings.playbackRate || 1.0;

                        // Add to queue in order received (CRITICAL for sequential playback)
                        audioQueueRef.current.push(audio);

                        // Play first chunk immediately
                        if (!firstChunkPlayed) {
                            firstChunkPlayed = true;

                            setIsSpeaking(true);
                            setIsLoading(false);
                            setError(null);
                            onStart?.();

                            audio.onended = () => {
                                playNextInQueue();
                            };

                            audio.onerror = () => {
                                playNextInQueue();
                            };

                            try {
                                await audio.play();
                                // Mark first chunk as played by setting index to 1
                                currentAudioIndexRef.current = 1;
                            } catch (playError: unknown) {
                                if (playError instanceof Error && playError.name === "NotAllowedError") {
                                    isPlayingQueueRef.current = false;
                                    setIsLoading(false);
                                    throw new Error("Click the speaker button again to play audio (browser autoplay policy)");
                                }
                                throw playError;
                            }
                        }
                    }
                }
            } catch (err) {
                const errorMsg = `TTS error: ${err}`;
                setError(errorMsg);
                onError?.(errorMsg);
                setIsLoading(false);
                isPlayingQueueRef.current = false;
            }
        },
        [settings.cacheTTS, settings.voice, settings.playbackRate, settings.ttsProvider, messageId, onStart, onEnd, onError, cleanup, playNextInQueue]
    );

    // Public API
    const speak = useCallback(
        async (text: string) => {
            if (!text || !text.trim()) {
                return;
            }

            setError(null);

            if (isBrowserMode) {
                await speakBrowser(text);
            } else {
                await speakExternal(text);
            }
        },
        [isBrowserMode, speakBrowser, speakExternal]
    );

    const stop = useCallback(() => {
        if (isBrowserMode) {
            window.speechSynthesis.cancel();
            setIsSpeaking(false);
        } else {
            // Stop queue playback
            isPlayingQueueRef.current = false;

            // Stop current audio
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current.currentTime = 0;
            }

            // Stop all queued audio
            audioQueueRef.current.forEach(audio => {
                audio.pause();
            });

            setIsSpeaking(false);
        }
    }, [isBrowserMode]);

    const pause = useCallback(() => {
        if (isBrowserMode) {
            window.speechSynthesis.pause();
        } else {
            // Pause current playing audio in queue
            const currentIndex = currentAudioIndexRef.current - 1;
            if (currentIndex >= 0 && currentIndex < audioQueueRef.current.length) {
                audioQueueRef.current[currentIndex].pause();
            } else if (audioRef.current) {
                audioRef.current.pause();
            }
        }
        setIsSpeaking(false);
    }, [isBrowserMode]);

    const resume = useCallback(() => {
        if (isBrowserMode) {
            window.speechSynthesis.resume();
            setIsSpeaking(true);
        } else {
            // Resume current playing audio in queue
            const currentIndex = currentAudioIndexRef.current - 1;
            if (currentIndex >= 0 && currentIndex < audioQueueRef.current.length) {
                audioQueueRef.current[currentIndex].play();
                setIsSpeaking(true);
            } else if (audioRef.current) {
                audioRef.current.play();
                setIsSpeaking(true);
            }
        }
    }, [isBrowserMode]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            cleanup();
        };
    }, [cleanup]);

    return {
        isSpeaking,
        isLoading,
        error,
        voices,
        speak,
        stop,
        pause,
        resume,
    };
}
