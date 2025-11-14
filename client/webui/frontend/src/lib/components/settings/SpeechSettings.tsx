import React, { useEffect, useState } from "react";
import { Mic, Volume2 } from "lucide-react";
import { useAudioSettings } from "@/lib/hooks";
import { Label, Switch, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Input } from "@/lib/components/ui";

export const SpeechSettingsPanel: React.FC = () => {
    const { settings, updateSetting } = useAudioSettings();
    const [availableVoices, setAvailableVoices] = useState<string[]>([]);
    const [loadingVoices, setLoadingVoices] = useState(false);

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
                        onValueChange={(value: "browser" | "external") => updateSetting("engineSTT", value)}
                        disabled={!settings.speechToText}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="browser">Browser</SelectItem>
                            <SelectItem value="external">External API</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

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
                        onValueChange={(value: "browser" | "external") => updateSetting("engineTTS", value)}
                        disabled={!settings.textToSpeech}
                    >
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="browser">Browser</SelectItem>
                            <SelectItem value="external">External API</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

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

                {/* Cache TTS */}
                <div className="flex items-center justify-between">
                    <Label className="font-medium">Cache Audio</Label>
                    <Switch
                        checked={settings.cacheTTS}
                        onCheckedChange={(checked) => updateSetting("cacheTTS", checked)}
                        disabled={!settings.textToSpeech || settings.engineTTS === "browser"}
                    />
                </div>

            </div>
        </div>
    );
};