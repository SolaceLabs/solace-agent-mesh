import { useState, useRef, useCallback, useEffect } from "react";
import { useAudioSettings } from "./useAudioSettings";

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

    const isBrowserMode = settings.engineTTS === "browser";

    // Load browser voices
    useEffect(() => {
        if (!isBrowserMode) return;

        const loadVoices = () => {
            const synth = window.speechSynthesis;
            if (!synth) return;

            const availableVoices = synth.getVoices();
            const voiceOptions: VoiceOption[] = availableVoices
                .filter((voice) => {
                    // Filter based on cloudBrowserVoices setting
                    if (settings.cloudBrowserVoices) {
                        return true; // Include all voices
                    }
                    return voice.localService; // Only local voices
                })
                .map((voice) => ({
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
                const provider = settings.ttsProvider || 'gemini';
                const response = await fetch(`/api/speech/voices?provider=${provider}`);
                if (response.ok) {
                    const data = await response.json();
                    const voiceOptions: VoiceOption[] = (data.voices || []).map((voice: string) => ({
                        value: voice,
                        label: voice,
                    }));
                    setVoices(voiceOptions);
                }
            } catch (err) {
                console.error("Failed to load external voices:", err);
            }
        };

        loadExternalVoices();
    }, [isBrowserMode, settings.ttsProvider]);  // Re-load when provider changes

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

                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = settings.playbackRate || 1.0;
                utterance.lang = settings.languageSTT || "en-US";

                // Set voice if specified
                if (settings.voice) {
                    const availableVoices = synth.getVoices();
                    const selectedVoice = availableVoices.find((v) => v.name === settings.voice);
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

                utterance.onerror = (event) => {
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

    // External TTS implementation
    const speakExternal = useCallback(
        async (text: string) => {
            setIsLoading(true);

            try {
                // Check cache first if enabled
                if (settings.cacheTTS) {
                    const cache = await caches.open("tts-responses");
                    const cacheKey = `${text}-${settings.voice}-${settings.ttsProvider || 'default'}`;
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

                // Generate new audio
                const requestBody: Record<string, unknown> = {
                    input: text,
                    voice: settings.voice,
                    messageId: messageId,
                };
                
                // Only include provider if defined (for backward compatibility)
                if (settings.ttsProvider) {
                    requestBody.provider = settings.ttsProvider;
                }
                
                const response = await fetch("/api/speech/tts", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(requestBody),
                });

                if (!response.ok) {
                    throw new Error(`TTS generation failed: ${response.statusText}`);
                }

                const audioBlob = await response.blob();

                // Cache if enabled
                if (settings.cacheTTS) {
                    const cache = await caches.open("tts-responses");
                    const cacheKey = `${text}-${settings.voice}-${settings.ttsProvider || 'default'}`;
                    
                    // Create Response with proper headers for cache compatibility
                    const responseToCache = new Response(audioBlob.slice(0), {
                        headers: {
                            'Content-Type': 'audio/mpeg',
                            'Content-Length': audioBlob.size.toString()
                        }
                    });
                    
                    await cache.put(cacheKey, responseToCache);
                }

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
                    const errorMsg = "Failed to play audio";
                    setError(errorMsg);
                    onError?.(errorMsg);
                    setIsSpeaking(false);
                    setIsLoading(false);
                    URL.revokeObjectURL(blobUrl);
                };

                audioRef.current = audio;
                audioUrlRef.current = blobUrl;
                await audio.play();
            } catch (err) {
                const errorMsg = `TTS error: ${err}`;
                setError(errorMsg);
                onError?.(errorMsg);
                setIsLoading(false);
            }
        },
        [settings.cacheTTS, settings.voice, settings.playbackRate, settings.ttsProvider, messageId, onStart, onEnd, onError]
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
        } else if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            setIsSpeaking(false);
        }
    }, [isBrowserMode]);

    const pause = useCallback(() => {
        if (isBrowserMode) {
            window.speechSynthesis.pause();
        } else if (audioRef.current) {
            audioRef.current.pause();
        }
        setIsSpeaking(false);
    }, [isBrowserMode]);

    const resume = useCallback(() => {
        if (isBrowserMode) {
            window.speechSynthesis.resume();
            setIsSpeaking(true);
        } else if (audioRef.current) {
            audioRef.current.play();
            setIsSpeaking(true);
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