import { useState, useRef, useCallback, useEffect } from "react";
import { useAudioSettings } from "./useAudioSettings";
import { getErrorMessage } from "@/lib/utils/api";
import { api } from "@/lib/api";

interface UseSpeechToTextOptions {
    onTranscriptionComplete?: (text: string) => void;
    onTranscriptionUpdate?: (text: string) => void;
    onError?: (error: string) => void;
}

interface UseSpeechToTextReturn {
    isListening: boolean;
    isLoading: boolean;
    error: string | null;
    transcript: string;
    startRecording: () => Promise<void>;
    stopRecording: () => Promise<void>;
    resetTranscript: () => void;
}

// Browser Speech Recognition types
interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
    resultIndex: number;
}

interface SpeechRecognitionResultList {
    length: number;
    item(index: number): SpeechRecognitionResult;
    [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
    isFinal: boolean;
    length: number;
    item(index: number): SpeechRecognitionAlternative;
    [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
    transcript: string;
    confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
    error: string;
    message: string;
}

interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start(): void;
    stop(): void;
    abort(): void;
    onstart: ((this: SpeechRecognition, ev: Event) => void) | null;
    onend: ((this: SpeechRecognition, ev: Event) => void) | null;
    onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => void) | null;
    onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null;
}

declare global {
    interface Window {
        SpeechRecognition: new () => SpeechRecognition;
        webkitSpeechRecognition: new () => SpeechRecognition;
    }
}

// Get best supported audio MIME type for recording
function getBestSupportedMimeType(): string {
    const types = ["audio/webm", "audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus", "audio/ogg", "audio/wav"];

    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }

    // Fallback based on browser
    const ua = navigator.userAgent.toLowerCase();
    if (ua.indexOf("safari") !== -1 && ua.indexOf("chrome") === -1) {
        return "audio/mp4";
    } else if (ua.indexOf("firefox") !== -1) {
        return "audio/ogg";
    }

    return "audio/webm";
}

function getFileExtension(mimeType: string): string {
    const mimeToExt: Record<string, string> = {
        "audio/webm": "webm",
        "audio/mp4": "mp4",
        "audio/ogg": "ogg",
        "audio/wav": "wav",
    };

    for (const [mime, ext] of Object.entries(mimeToExt)) {
        if (mimeType.includes(mime)) {
            return ext;
        }
    }

    return "webm";
}

export function useSpeechToText(options: UseSpeechToTextOptions = {}): UseSpeechToTextReturn {
    const { onTranscriptionComplete, onTranscriptionUpdate, onError } = options;
    const { settings, updateSetting } = useAudioSettings();

    const [isListening, setIsListening] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [transcript, setTranscript] = useState("");

    // Browser STT refs
    const recognitionRef = useRef<SpeechRecognition | null>(null);

    // External STT refs
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioStreamRef = useRef<MediaStream | null>(null);

    const isBrowserMode = settings.engineSTT === "browser";

    // Cleanup function
    const cleanup = useCallback(() => {
        if (recognitionRef.current) {
            try {
                recognitionRef.current.stop();
            } catch {
                // Ignore errors during cleanup
            }
            recognitionRef.current = null;
        }

        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
            try {
                mediaRecorderRef.current.stop();
            } catch {
                // Ignore errors during cleanup
            }
        }

        if (audioStreamRef.current) {
            audioStreamRef.current.getTracks().forEach(track => track.stop());
            audioStreamRef.current = null;
        }

        audioChunksRef.current = [];
    }, []);

    // Browser STT implementation
    const startBrowserRecording = useCallback(async () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            const errorMsg = "Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari, or switch to External API mode in settings.";
            setError(errorMsg);
            onError?.(errorMsg);
            console.error("Browser STT not supported. Available:", {
                SpeechRecognition: !!window.SpeechRecognition,
                webkitSpeechRecognition: !!window.webkitSpeechRecognition,
                userAgent: navigator.userAgent,
            });
            return;
        }

        try {
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = settings.languageSTT || "en-US";

            recognition.onstart = () => {
                setIsListening(true);
                setError(null);
            };

            recognition.onresult = (event: SpeechRecognitionEvent) => {
                let interimTranscript = "";
                let finalTranscript = "";

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const result = event.results[i];
                    const transcriptPart = result[0].transcript;

                    if (result.isFinal) {
                        finalTranscript += transcriptPart + " ";
                    } else {
                        interimTranscript += transcriptPart;
                    }
                }

                const fullTranscript = (finalTranscript + interimTranscript).trim();
                setTranscript(fullTranscript);
                onTranscriptionUpdate?.(fullTranscript);

                if (finalTranscript) {
                    onTranscriptionComplete?.(finalTranscript.trim());
                }
            };

            recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
                const errorMsg = `Speech recognition error: ${event.error}`;
                setError(errorMsg);
                onError?.(errorMsg);
                setIsListening(false);
            };

            recognition.onend = () => {
                setIsListening(false);
            };

            recognitionRef.current = recognition;
            recognition.start();
        } catch (err) {
            const errorMsg = `Failed to start speech recognition: ${err}`;
            setError(errorMsg);
            onError?.(errorMsg);
        }
    }, [settings.languageSTT, onTranscriptionComplete, onTranscriptionUpdate, onError]);

    const stopBrowserRecording = useCallback(async () => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
            recognitionRef.current = null;
        }
        setIsListening(false);
    }, []);

    // External STT implementation
    const startExternalRecording = useCallback(async () => {
        // Check if external STT is configured
        try {
            const config = await api.webui.get("/api/v1/speech/config");

            if (!config.sttExternal) {
                // Auto-switch to browser mode
                updateSetting("engineSTT", "browser");

                const errorMsg = "External STT is not configured. Switched to Browser mode. Please click the microphone button again.";
                setError(errorMsg);
                onError?.(errorMsg);

                // Don't try to start recording - user needs to click again
                return;
            }
        } catch (error) {
            const errorMsg = `Failed to check STT configuration: ${getErrorMessage(error, "Please try again.")}`;
            setError(errorMsg);
            onError?.(errorMsg);
            return;
        }

        try {
            // Request microphone permission
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false,
            });

            audioStreamRef.current = stream;
            audioChunksRef.current = [];

            const mimeType = getBestSupportedMimeType();
            const mediaRecorder = new MediaRecorder(stream, { mimeType });

            mediaRecorder.ondataavailable = (event: BlobEvent) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                setIsLoading(true);

                try {
                    if (audioChunksRef.current.length === 0) {
                        throw new Error("No audio data recorded");
                    }

                    const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
                    const fileExtension = getFileExtension(mimeType);

                    // Send to backend with provider preference and language
                    const formData = new FormData();
                    formData.append("audio", audioBlob, `audio.${fileExtension}`);
                    if (settings.sttProvider && settings.sttProvider !== "browser") {
                        formData.append("provider", settings.sttProvider);
                    }
                    // Send language setting for external STT
                    if (settings.languageSTT) {
                        formData.append("language", settings.languageSTT);
                    }

                    const response = await api.webui.post("/api/v1/speech/stt", formData, { fullResponse: true });

                    if (!response.ok) {
                        const errorText = await response.text();
                        let backendMessage = "";
                        try {
                            const errorJson = JSON.parse(errorText);
                            backendMessage = errorJson.detail || errorJson.message || errorJson.error || "";
                        } catch {
                            backendMessage = errorText;
                        }
                        throw new Error(backendMessage || `Transcription failed: ${response.statusText}`);
                    }

                    const result = await response.json();
                    const transcribedText = result.text || "";

                    setTranscript(transcribedText);
                    onTranscriptionComplete?.(transcribedText);
                } catch (err) {
                    const errorMsg = `Transcription error: ${err}`;
                    setError(errorMsg);
                    onError?.(errorMsg);
                } finally {
                    setIsLoading(false);
                    cleanup();
                }
            };

            mediaRecorderRef.current = mediaRecorder;
            mediaRecorder.start(100); // Collect data every 100ms
            setIsListening(true);
            setError(null);
        } catch (err) {
            const errorMsg = `Failed to access microphone: ${err}`;
            setError(errorMsg);
            onError?.(errorMsg);
            cleanup();
        }
    }, [settings.sttProvider, settings.languageSTT, onTranscriptionComplete, onError, cleanup, updateSetting]);

    const stopExternalRecording = useCallback(async () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
            mediaRecorderRef.current.stop();
        }
        setIsListening(false);
    }, []);

    // Public API
    const startRecording = useCallback(async () => {
        setError(null);
        setTranscript("");

        if (isBrowserMode) {
            await startBrowserRecording();
        } else {
            await startExternalRecording();
        }
    }, [isBrowserMode, startBrowserRecording, startExternalRecording]);

    const stopRecording = useCallback(async () => {
        if (isBrowserMode) {
            await stopBrowserRecording();
        } else {
            await stopExternalRecording();
        }
    }, [isBrowserMode, stopBrowserRecording, stopExternalRecording]);

    const resetTranscript = useCallback(() => {
        setTranscript("");
        setError(null);
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            cleanup();
        };
    }, [cleanup]);

    return {
        isListening,
        isLoading,
        error,
        transcript,
        startRecording,
        stopRecording,
        resetTranscript,
    };
}
