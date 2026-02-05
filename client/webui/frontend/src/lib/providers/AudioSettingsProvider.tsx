import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

export interface SpeechSettings {
    // STT Settings
    speechToText: boolean;
    engineSTT: "browser" | "external";
    sttProvider: "browser" | "openai" | "azure";
    languageSTT: string;

    // TTS Settings
    textToSpeech: boolean;
    engineTTS: "browser" | "external";
    ttsProvider: "browser" | "gemini" | "azure" | "polly";
    voice: string;
    playbackRate: number;
    automaticPlayback: boolean;
    cacheTTS: boolean;
    cloudBrowserVoices: boolean;

    // Advanced
    conversationMode: boolean;
}

export interface AudioSettingsContextValue {
    settings: SpeechSettings;
    isInitialized: boolean;
    updateSetting: <K extends keyof SpeechSettings>(key: K, value: SpeechSettings[K]) => void;
    updateSettings: (updates: Partial<SpeechSettings>) => void;
    resetSettings: () => void;
    speechToTextEndpoint: "browser" | "external";
    textToSpeechEndpoint: "browser" | "external";
    isTTSPlaying: boolean;
    setIsTTSPlaying: (playing: boolean) => void;
    onTTSStart: () => void;
    onTTSEnd: () => void;
}

export const AudioSettingsContext = createContext<AudioSettingsContextValue | undefined>(undefined);

const STORAGE_KEY_MAP: Record<keyof SpeechSettings, string> = {
    speechToText: "speechToText",
    engineSTT: "engineSTT",
    sttProvider: "sttProvider",
    languageSTT: "languageSTT",

    textToSpeech: "textToSpeech",
    engineTTS: "engineTTS",
    ttsProvider: "ttsProvider",
    voice: "voice",
    playbackRate: "playbackRate",
    automaticPlayback: "automaticPlayback",
    cacheTTS: "cacheTTS",
    cloudBrowserVoices: "cloudBrowserVoices",

    conversationMode: "conversationMode",
};

const DEFAULT_SETTINGS: SpeechSettings = {
    speechToText: false,
    engineSTT: "browser",
    sttProvider: "browser",
    languageSTT: "en-US",

    textToSpeech: true, // Enable by default for browser TTS
    engineTTS: "browser", // Use browser TTS by default (no backend needed)
    ttsProvider: "browser",
    voice: "",
    playbackRate: 1.0,
    automaticPlayback: false, // Disabled by default - doesn't work reliably due to browser autoplay policies
    cacheTTS: true,
    cloudBrowserVoices: false,

    conversationMode: false,
};

function loadSettingsFromStorage(): SpeechSettings {
    const settings = { ...DEFAULT_SETTINGS };

    try {
        Object.entries(STORAGE_KEY_MAP).forEach(([settingKey, storageKey]) => {
            const value = localStorage.getItem(storageKey);
            if (value !== null) {
                const key = settingKey as keyof SpeechSettings;

                if (typeof DEFAULT_SETTINGS[key] === "boolean") {
                    (settings as Record<string, unknown>)[key] = value === "true";
                } else if (typeof DEFAULT_SETTINGS[key] === "number") {
                    (settings as Record<string, unknown>)[key] = parseFloat(value);
                } else {
                    (settings as Record<string, unknown>)[key] = value;
                }
            }
        });
    } catch (error) {
        console.error("Error loading audio settings from storage:", error);
    }

    return settings;
}

export const AudioSettingsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [settings, setSettings] = useState<SpeechSettings>(loadSettingsFromStorage);
    const [isInitialized, setIsInitialized] = useState(false);
    const [isTTSPlaying, setIsTTSPlaying] = useState(false);

    // Fetch server configuration on mount and validate external mode availability
    useEffect(() => {
        const fetchServerConfig = async () => {
            try {
                // Fetch main config
                const config = await api.webui.get("/api/v1/config");
                const ttsSettings = config.tts_settings || {};

                // Check speech config for external availability AND get speechTab defaults
                let sttExternal = false;
                let ttsExternal = false;
                let speechTabSettings: Record<string, unknown> = {};
                try {
                    const speechConfig = await api.webui.get("/api/v1/speech/config");
                    sttExternal = speechConfig.sttExternal || false;
                    ttsExternal = speechConfig.ttsExternal || false;

                    // Extract speechTab settings from the speech config response
                    // These come from the YAML config's speech.speechTab section
                    speechTabSettings = {
                        // STT settings
                        speechToText: speechConfig.speechToText,
                        engineSTT: speechConfig.engineSTT,
                        sttProvider: speechConfig.sttProvider,
                        languageSTT: speechConfig.languageSTT,
                        // TTS settings
                        textToSpeech: speechConfig.textToSpeech,
                        engineTTS: speechConfig.engineTTS,
                        ttsProvider: speechConfig.ttsProvider,
                        voice: speechConfig.voice,
                        playbackRate: speechConfig.playbackRate,
                        automaticPlayback: speechConfig.automaticPlayback,
                        cacheTTS: speechConfig.cacheTTS,
                        cloudBrowserVoices: speechConfig.cloudBrowserVoices,
                        // Advanced
                        conversationMode: speechConfig.conversationMode,
                    };
                } catch (error) {
                    console.error("Error fetching speech config:", error);
                }

                setSettings(prev => {
                    const updated = { ...prev };

                    // First, apply speechTab settings from server (YAML defaults)
                    // Only apply if localStorage doesn't have a user-set value
                    Object.entries(speechTabSettings).forEach(([key, value]) => {
                        if (value === undefined) return; // Skip undefined values
                        const settingKey = key as keyof SpeechSettings;
                        const storageKey = STORAGE_KEY_MAP[settingKey];
                        if (settingKey in updated && storageKey && localStorage.getItem(storageKey) === null) {
                            (updated as Record<string, unknown>)[settingKey] = value;
                        }
                    });

                    // Then apply TTS settings from main config (these may override speechTab)
                    Object.entries(ttsSettings).forEach(([key, value]) => {
                        const settingKey = key as keyof SpeechSettings;
                        const storageKey = STORAGE_KEY_MAP[settingKey];
                        if (settingKey in updated && storageKey && localStorage.getItem(storageKey) === null) {
                            (updated as Record<string, unknown>)[settingKey] = value;
                        }
                    });

                    // Force browser mode if external is selected but not configured
                    if (updated.engineSTT === "external" && !sttExternal) {
                        console.warn("External STT not configured, falling back to browser mode");
                        updated.engineSTT = "browser";
                        updated.sttProvider = "browser";
                        localStorage.setItem(STORAGE_KEY_MAP.engineSTT, "browser");
                        localStorage.setItem(STORAGE_KEY_MAP.sttProvider, "browser");
                    }
                    if (updated.engineTTS === "external" && !ttsExternal) {
                        console.warn("External TTS not configured, falling back to browser mode");
                        updated.engineTTS = "browser";
                        updated.ttsProvider = "browser";
                        localStorage.setItem(STORAGE_KEY_MAP.engineTTS, "browser");
                        localStorage.setItem(STORAGE_KEY_MAP.ttsProvider, "browser");
                    }

                    return updated;
                });
            } catch (error) {
                console.error("Error fetching TTS config from config endpoint:", error);
            } finally {
                setIsInitialized(true);
            }
        };

        fetchServerConfig();
    }, []);

    const updateSetting = useCallback(<K extends keyof SpeechSettings>(key: K, value: SpeechSettings[K]) => {
        setSettings(prev => {
            const updated = { ...prev, [key]: value };
            const storageKey = STORAGE_KEY_MAP[key];
            if (storageKey) {
                localStorage.setItem(storageKey, String(value));
                console.log(`Saved ${key} = ${value} to localStorage as ${storageKey}`);
            }
            return updated;
        });
    }, []);

    const updateSettings = useCallback((updates: Partial<SpeechSettings>) => {
        setSettings(prev => {
            const updated = { ...prev, ...updates };
            Object.entries(updates).forEach(([key, value]) => {
                const storageKey = STORAGE_KEY_MAP[key as keyof SpeechSettings];
                if (storageKey) {
                    localStorage.setItem(storageKey, String(value));
                }
            });
            return updated;
        });
    }, []);

    const resetSettings = useCallback(() => {
        setSettings(DEFAULT_SETTINGS);
        Object.values(STORAGE_KEY_MAP).forEach(storageKey => {
            localStorage.removeItem(storageKey);
        });
    }, []);

    const onTTSStart = useCallback(() => {
        setIsTTSPlaying(true);
    }, []);

    const onTTSEnd = useCallback(() => {
        setIsTTSPlaying(false);
    }, []);

    const value: AudioSettingsContextValue = {
        settings,
        isInitialized,
        updateSetting,
        updateSettings,
        resetSettings,
        speechToTextEndpoint: settings.engineSTT,
        textToSpeechEndpoint: settings.engineTTS,
        isTTSPlaying,
        setIsTTSPlaying,
        onTTSStart,
        onTTSEnd,
    };

    return <AudioSettingsContext.Provider value={value}>{children}</AudioSettingsContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export function useAudioSettings(): AudioSettingsContextValue {
    const context = useContext(AudioSettingsContext);
    if (!context) {
        throw new Error("useAudioSettings must be used within AudioSettingsProvider");
    }
    return context;
}
