import React, { useEffect, useState } from "react";
import { Mic, Volume2, AlertCircle, Info } from "lucide-react";
import { useAudioSettings } from "@/lib/hooks";
import { Label, Switch, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Input } from "@/lib/components/ui";

export const SpeechSettingsPanel: React.FC = () => {
    const { settings, updateSetting } = useAudioSettings();
    const [availableVoices, setAvailableVoices] = useState<string[]>([]);
    const [loadingVoices, setLoadingVoices] = useState(false);
    const [sttConfigured, setSttConfigured] = useState<boolean | null>(null);
    const [ttsConfigured, setTtsConfigured] = useState<boolean | null>(null);

    // Check STT/TTS configuration status
    useEffect(() => {
        const checkConfig = async () => {
            try {
                const response = await fetch("/api/speech/config");
                if (response.ok) {
                    const config = await response.json();
                    setSttConfigured(config.sttExternal || false);
                    setTtsConfigured(config.ttsExternal || false);
                }
            } catch (error) {
                console.error("Error checking speech config:", error);
            }
        };
        checkConfig();
    }, []);

    // Load voices when provider or engine changes
    useEffect(() => {
        const loadVoices = async () => {
            if (settings.engineTTS !== "external") {
                // For browser mode, use hardcoded list or browser voices
                setAvailableVoices([]);
                return;
            }

            setLoadingVoices(true);
            try {
                const provider = settings.ttsProvider || 'gemini';
                const response = await fetch(`/api/speech/voices?provider=${provider}`);
                if (response.ok) {
                    const data = await response.json();
                    setAvailableVoices(data.voices || []);
                } else {
                    console.error("Failed to load voices:", response.statusText);
                }
            } catch (error) {
                console.error("Error loading voices:", error);
            } finally {
                setLoadingVoices(false);
            }
        };

        loadVoices();
    }, [settings.engineTTS, settings.ttsProvider]);

    return (
        <div className="space-y-6">
            {/* Speech-to-Text Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 border-b pb-2">
                    <Mic className="size-5" />
                    <h3 className="text-lg font-semibold">Speech-to-Text</h3>
                </div>

                {/* Enable STT */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Enable Speech-to-Text</Label>
                    <Switch
                        checked={settings.speechToText}
                        onCheckedChange={(checked) => updateSetting("speechToText", checked)}
                    />
                </div>

                {/* STT Engine */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">STT Engine</Label>
                    <Select
                        value={settings.engineSTT}
                        onValueChange={(value: "browser" | "external") => {
                            // If switching to external but not configured, show warning and stay on browser
                            if (value === "external" && sttConfigured === false) {
                                alert("External STT is not configured. Please add STT configuration to webui.yaml first.");
                                return;
                            }
                            updateSetting("engineSTT", value);
                        }}
                        disabled={!settings.speechToText}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="browser">Browser</SelectItem>
                            <SelectItem value="external" disabled={sttConfigured === false}>
                                External API {sttConfigured === false ? "(Not Configured)" : ""}
                            </SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* STT Configuration Warning - Only show for External API */}
                {settings.speechToText && settings.engineSTT === "external" && sttConfigured === false && (
                    <div className="rounded-md bg-yellow-50 dark:bg-yellow-950/20 p-3 border border-yellow-200 dark:border-yellow-900">
                        <div className="flex gap-2">
                            <AlertCircle className="size-5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 text-sm">
                                <p className="font-semibold text-yellow-800 dark:text-yellow-400 mb-1">
                                    External STT Not Configured
                                </p>
                                <p className="text-yellow-700 dark:text-yellow-500 mb-2">
                                    To use External API mode, add the following to your <code className="px-1 py-0.5 bg-yellow-100 dark:bg-yellow-900/40 rounded text-xs">webui.yaml</code>:
                                </p>
                                <pre className="text-xs bg-yellow-100 dark:bg-yellow-900/40 p-2 rounded overflow-x-auto">
{`speech:
  stt:
    url: https://api.openai.com/v1/audio/transcriptions
    api_key: \${OPENAI_API_KEY}
    model: whisper-1`}
                                </pre>
                                <p className="text-yellow-700 dark:text-yellow-500 mt-2 text-xs">
                                    Set <code className="px-1 py-0.5 bg-yellow-100 dark:bg-yellow-900/40 rounded">OPENAI_API_KEY</code> environment variable or use Browser mode (free, no setup required).
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Browser STT Info */}
                {settings.speechToText && settings.engineSTT === "browser" && (
                    <div className="rounded-md bg-blue-50 dark:bg-blue-950/20 p-3 border border-blue-200 dark:border-blue-900">
                        <div className="flex gap-2">
                            <Info className="size-5 text-blue-600 dark:text-blue-500 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 text-sm text-blue-700 dark:text-blue-400">
                                <p className="font-semibold mb-1">Browser Mode (Free)</p>
                                <p className="text-xs">
                                    Uses your browser's built-in speech recognition. Works in Chrome, Edge, and Safari. No API key or backend configuration required.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Language */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Language</Label>
                    <Select
                        value={settings.languageSTT}
                        onValueChange={(value) => updateSetting("languageSTT", value)}
                        disabled={!settings.speechToText}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="en-US">English (US)</SelectItem>
                            <SelectItem value="en-GB">English (UK)</SelectItem>
                            <SelectItem value="es-ES">Spanish</SelectItem>
                            <SelectItem value="fr-FR">French</SelectItem>
                            <SelectItem value="de-DE">German</SelectItem>
                            <SelectItem value="it-IT">Italian</SelectItem>
                            <SelectItem value="ja-JP">Japanese</SelectItem>
                            <SelectItem value="ko-KR">Korean</SelectItem>
                            <SelectItem value="zh-CN">Chinese (Simplified)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Auto-send delay */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Auto-send Delay (seconds)</Label>
                    <Input
                        type="number"
                        min={-1}
                        max={10}
                        value={settings.autoSendText}
                        onChange={(e) => updateSetting("autoSendText", parseInt(e.target.value) || -1)}
                        disabled={!settings.speechToText}
                        className="w-40"
                    />
                </div>

                {/* Auto-transcribe */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Auto-transcribe Audio</Label>
                    <Switch
                        checked={settings.autoTranscribeAudio}
                        onCheckedChange={(checked) => updateSetting("autoTranscribeAudio", checked)}
                        disabled={!settings.speechToText}
                    />
                </div>

                {/* Decibel threshold */}
                {settings.autoTranscribeAudio && (
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Silence Threshold (dB)</Label>
                        <Input
                            type="number"
                            min={-60}
                            max={-20}
                            step={5}
                            value={settings.decibelThreshold}
                            onChange={(e) => updateSetting("decibelThreshold", parseInt(e.target.value) || -45)}
                            disabled={!settings.speechToText}
                            className="w-40"
                        />
                    </div>
                )}
            </div>

            {/* Text-to-Speech Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 border-b pb-2">
                    <Volume2 className="size-5" />
                    <h3 className="text-lg font-semibold">Text-to-Speech</h3>
                </div>

                {/* Enable TTS */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Enable Text-to-Speech</Label>
                    <Switch
                        checked={settings.textToSpeech}
                        onCheckedChange={(checked) => updateSetting("textToSpeech", checked)}
                    />
                </div>

                {/* TTS Engine */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">TTS Engine</Label>
                    <Select
                        value={settings.engineTTS}
                        onValueChange={(value: "browser" | "external") => {
                            // If switching to external but not configured, show warning and stay on browser
                            if (value === "external" && ttsConfigured === false) {
                                alert("External TTS is not configured. Please add TTS configuration to webui.yaml first.");
                                return;
                            }
                            updateSetting("engineTTS", value);
                        }}
                        disabled={!settings.textToSpeech}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="browser">Browser</SelectItem>
                            <SelectItem value="external" disabled={ttsConfigured === false}>
                                External API {ttsConfigured === false ? "(Not Configured)" : ""}
                            </SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* TTS Configuration Warning - Only show for External API */}
                {settings.textToSpeech && settings.engineTTS === "external" && ttsConfigured === false && (
                    <div className="rounded-md bg-yellow-50 dark:bg-yellow-950/20 p-3 border border-yellow-200 dark:border-yellow-900">
                        <div className="flex gap-2">
                            <AlertCircle className="size-5 text-yellow-600 dark:text-yellow-500 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 text-sm">
                                <p className="font-semibold text-yellow-800 dark:text-yellow-400 mb-1">
                                    External TTS Not Configured
                                </p>
                                <p className="text-yellow-700 dark:text-yellow-500 mb-2">
                                    To use External API mode, configure TTS in your <code className="px-1 py-0.5 bg-yellow-100 dark:bg-yellow-900/40 rounded text-xs">webui.yaml</code>. Example for Gemini:
                                </p>
                                <pre className="text-xs bg-yellow-100 dark:bg-yellow-900/40 p-2 rounded overflow-x-auto">
{`speech:
  tts:
    provider: gemini
    api_key: \${GEMINI_API_KEY}
    model: gemini-2.0-flash-exp`}
                                </pre>
                                <p className="text-yellow-700 dark:text-yellow-500 mt-2 text-xs">
                                    Or use Browser mode (free, no setup required).
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Browser TTS Info */}
                {settings.textToSpeech && settings.engineTTS === "browser" && (
                    <div className="rounded-md bg-blue-50 dark:bg-blue-950/20 p-3 border border-blue-200 dark:border-blue-900">
                        <div className="flex gap-2">
                            <Info className="size-5 text-blue-600 dark:text-blue-500 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 text-sm text-blue-700 dark:text-blue-400">
                                <p className="font-semibold mb-1">Browser Mode (Free)</p>
                                <p className="text-xs">
                                    Uses your browser's built-in text-to-speech. No API key or backend configuration required. Voice quality depends on your browser and operating system.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* TTS Provider Selection - Only show for External API */}
                {settings.engineTTS === "external" && (
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">TTS Provider</Label>
                        <Select
                            value={settings.ttsProvider}
                            onValueChange={(value: "gemini" | "azure") => updateSetting("ttsProvider", value)}
                            disabled={!settings.textToSpeech}
                        >
                            <SelectTrigger className="w-40">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="gemini">Google Gemini</SelectItem>
                                <SelectItem value="azure">Azure Neural</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                )}

                {/* Voice Selection - Only show for External API */}
                {settings.engineTTS === "external" && (
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Voice</Label>
                        <Select
                            value={settings.voice}
                            onValueChange={(value) => updateSetting("voice", value)}
                            disabled={!settings.textToSpeech || loadingVoices}
                        >
                            <SelectTrigger className="w-40">
                                <SelectValue placeholder={loadingVoices ? "Loading..." : "Select voice"} />
                            </SelectTrigger>
                            <SelectContent>
                                {availableVoices.length > 0 ? (
                                // External mode - show loaded voices with grouping for Azure
                                (() => {
                                    // Check if this is Azure provider (voices contain DragonHD)
                                    const isAzure = availableVoices.some(v => v.includes('DragonHD'));
                                    
                                    if (isAzure && settings.ttsProvider === 'azure') {
                                        // Group Azure voices into HD and Normal
                                        const hdVoices = availableVoices.filter(v => v.includes('DragonHD'));
                                        const normalVoices = availableVoices.filter(v => !v.includes('DragonHD'));
                                        
                                        return (
                                            <>
                                                {hdVoices.length > 0 && (
                                                    <>
                                                        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                                                            HD Voices (Premium)
                                                        </div>
                                                        {hdVoices.map((voice) => (
                                                            <SelectItem key={voice} value={voice}>
                                                                {voice.replace(':DragonHDLatestNeural', ' (HD)')}
                                                            </SelectItem>
                                                        ))}
                                                    </>
                                                )}
                                                {normalVoices.length > 0 && (
                                                    <>
                                                        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t mt-1 pt-2">
                                                            Standard Voices
                                                        </div>
                                                        {normalVoices.map((voice) => (
                                                            <SelectItem key={voice} value={voice}>
                                                                {voice.replace('Neural', '')}
                                                            </SelectItem>
                                                        ))}
                                                    </>
                                                )}
                                            </>
                                        );
                                    } else {
                                        // Gemini or other providers - show all voices
                                        return availableVoices.map((voice) => (
                                            <SelectItem key={voice} value={voice}>
                                                {voice}
                                            </SelectItem>
                                        ));
                                    }
                                })()
                            ) : (
                                // No voices loaded yet
                                <SelectItem value="loading" disabled>
                                    {loadingVoices ? "Loading..." : "No voices available"}
                                </SelectItem>
                            )}
                            </SelectContent>
                        </Select>
                    </div>
                )}

                {/* Playback Rate */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Playback Speed</Label>
                    <Input
                        type="number"
                        min={0.5}
                        max={2.0}
                        step={0.1}
                        value={settings.playbackRate}
                        onChange={(e) => updateSetting("playbackRate", parseFloat(e.target.value) || 1.0)}
                        disabled={!settings.textToSpeech}
                        className="w-40"
                    />
                </div>

                {/* Automatic Playback */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Automatic Playback</Label>
                    <Switch
                        checked={settings.conversationMode || settings.automaticPlayback}
                        onCheckedChange={(checked) => updateSetting("automaticPlayback", checked)}
                        disabled={!settings.textToSpeech || settings.conversationMode}
                    />
                </div>

                {/* Cache TTS - Only show for External API */}
                {settings.engineTTS === "external" && (
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Cache Audio</Label>
                        <Switch
                            checked={settings.cacheTTS}
                            onCheckedChange={(checked) => updateSetting("cacheTTS", checked)}
                            disabled={!settings.textToSpeech}
                        />
                    </div>
                )}

            </div>
        </div>
    );
};