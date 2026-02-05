import { AudioSettingsContext, type AudioSettingsContextValue, type SpeechSettings } from "@/lib/providers/AudioSettingsProvider";

const defaultSpeechToTextSettings: SpeechSettings = {
    speechToText: true,
    engineSTT: "browser",
    sttProvider: "browser",
    languageSTT: "",

    // TTS Settings
    textToSpeech: false,
    engineTTS: "browser",
    ttsProvider: "browser",
    voice: "",
    playbackRate: 1,
    automaticPlayback: false,
    cacheTTS: false,
    cloudBrowserVoices: false,

    // Advanced
    conversationMode: false,
};

const defaultMockAudioSettingsValues: AudioSettingsContextValue = {
    settings: defaultSpeechToTextSettings,
    isInitialized: false,
    updateSetting: () => {},
    updateSettings: () => {},
    resetSettings: () => {},
    speechToTextEndpoint: "browser",
    textToSpeechEndpoint: "browser",
    isTTSPlaying: false,
    setIsTTSPlaying: () => {},
    onTTSStart: () => {},
    onTTSEnd: () => {},
};

interface MockAudioSettingsProviderProps {
    children: React.ReactNode;
    mockValues: Partial<AudioSettingsContextValue>;
}

export const MockAudioSettingsProvider: React.FC<MockAudioSettingsProviderProps> = ({ children, mockValues }) => {
    const contextValues = {
        ...defaultMockAudioSettingsValues,
        ...mockValues,
    };

    return <AudioSettingsContext.Provider value={contextValues}>{children}</AudioSettingsContext.Provider>;
};
