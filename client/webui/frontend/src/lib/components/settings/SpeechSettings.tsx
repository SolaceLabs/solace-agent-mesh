import React, { useEffect, useState, useRef } from "react";
import { Mic, Volume2, AlertCircle, Play, Loader2 } from "lucide-react";
import { useAudioSettings, useConfigContext } from "@/lib/hooks";
import { Label, Switch, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Input, Button } from "@/lib/components/ui";
import { api } from "@/lib/api";

export const SpeechSettingsPanel: React.FC = () => {
    const { settings, updateSetting } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();
    const [availableVoices, setAvailableVoices] = useState<string[]>([]);
    const [loadingVoices, setLoadingVoices] = useState(false);
    const [sttConfigured, setSttConfigured] = useState<boolean | null>(null);
    const [ttsConfigured, setTtsConfigured] = useState<boolean | null>(null);
    // Per-provider configuration status
    const [sttProviders, setSttProviders] = useState<{ openai: boolean; azure: boolean } | null>(null);
    const [ttsProviders, setTtsProviders] = useState<{ gemini: boolean; azure: boolean; polly: boolean } | null>(null);
    const [playingSample, setPlayingSample] = useState(false);
    const [loadingSample, setLoadingSample] = useState(false);
    const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;
    const ttsEnabled = configFeatureEnablement?.textToSpeech ?? true;

    // Check STT/TTS configuration status and auto-reset provider if needed
    useEffect(() => {
        const checkConfig = async () => {
            try {
                const config = await api.webui.get("/api/v1/speech/config");
                const sttExt = config.sttExternal || false;
                const ttsExt = config.ttsExternal || false;

                setSttConfigured(sttExt);
                setTtsConfigured(ttsExt);

                // Set per-provider status
                if (config.sttProviders) {
                    setSttProviders(config.sttProviders);
                }
                if (config.ttsProviders) {
                    setTtsProviders(config.ttsProviders);
                }

                // Auto-reset provider to browser if external not configured
                if (!sttExt && settings.sttProvider !== "browser") {
                    console.warn("External STT not configured, resetting provider to browser");
                    updateSetting("sttProvider", "browser");
                    updateSetting("engineSTT", "browser");
                }
                if (!ttsExt && settings.ttsProvider !== "browser") {
                    console.warn("External TTS not configured, resetting provider to browser");
                    updateSetting("ttsProvider", "browser");
                    updateSetting("engineTTS", "browser");
                }
            } catch (error) {
                console.error("Error checking speech config:", error);
            }
        };
        checkConfig();
    }, [settings.sttProvider, settings.ttsProvider, updateSetting]);

    // Track previous provider to detect changes
    const prevProviderRef = useRef(settings.ttsProvider);

    // Load voices when TTS provider changes and auto-select first voice if current voice is invalid
    useEffect(() => {
        const loadVoices = async () => {
            if (settings.ttsProvider === "browser") {
                // For browser mode, use hardcoded list or browser voices
                setAvailableVoices([]);
                prevProviderRef.current = settings.ttsProvider;
                return;
            }

            setLoadingVoices(true);
            try {
                const provider = settings.ttsProvider || "gemini";
                const data = await api.webui.get(`/api/v1/speech/voices?provider=${provider}`);
                const voices = data.voices || [];
                setAvailableVoices(voices);

                // Auto-select first voice if provider changed and current voice is not in the new provider's voice list
                const providerChanged = prevProviderRef.current !== settings.ttsProvider;
                if (providerChanged && voices.length > 0 && !voices.includes(settings.voice)) {
                    console.log(`Voice "${settings.voice}" not available for ${provider}, selecting first available: ${voices[0]}`);
                    updateSetting("voice", voices[0]);
                }

                prevProviderRef.current = settings.ttsProvider;
            } catch (error) {
                console.error("Error loading voices:", error);
            } finally {
                setLoadingVoices(false);
            }
        };

        loadVoices();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [settings.ttsProvider]);

    // Cleanup audio element on unmount
    useEffect(() => {
        return () => {
            if (audioElement) {
                audioElement.pause();
                audioElement.src = "";
            }
        };
    }, [audioElement]);

    // Function to play voice sample
    const playVoiceSample = async (voice: string) => {
        try {
            // Stop any currently playing audio and reset states
            if (audioElement) {
                audioElement.pause();
                audioElement.src = "";
                audioElement.onended = null;
                audioElement.onerror = null;
                setAudioElement(null);
            }

            setLoadingSample(true);
            setPlayingSample(false);

            // Create form data
            const formData = new FormData();
            formData.append("voice", voice);
            if (settings.ttsProvider !== "browser") {
                formData.append("provider", settings.ttsProvider);
            }

            // Fetch voice sample
            const response = await api.webui.post("/api/v1/speech/voice-sample", formData, { fullResponse: true });

            if (!response.ok) {
                throw new Error(`Failed to load voice sample: ${response.statusText}`);
            }

            // Create blob from response
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);

            setLoadingSample(false);
            setPlayingSample(true);

            // Create and play audio
            const audio = new Audio(url);
            audio.onended = () => {
                setPlayingSample(false);
                setAudioElement(null);
                URL.revokeObjectURL(url);
            };
            audio.onerror = () => {
                setPlayingSample(false);
                setAudioElement(null);
                URL.revokeObjectURL(url);
            };

            // Apply playback speed from settings
            audio.playbackRate = settings.playbackRate || 1.0;

            setAudioElement(audio);
            await audio.play();
        } catch (error) {
            console.error("Error playing voice sample:", error);
            setLoadingSample(false);
            setPlayingSample(false);
            setAudioElement(null);
            alert("Failed to play voice sample. Please try again.");
        }
    };

    return (
        <div className="space-y-6">
            {/* Speech-to-Text Section */}
            {sttEnabled && (
                <div className="space-y-4">
                    <div className="flex items-center gap-2 border-b pb-2">
                        <Mic className="size-5" />
                        <h3 className="text-lg font-semibold">Speech-to-Text</h3>
                    </div>

                    {/* Enable STT */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Enable Speech-to-Text</Label>
                        <Switch checked={settings.speechToText} onCheckedChange={checked => updateSetting("speechToText", checked)} />
                    </div>

                    {/* STT Provider */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Speech-to-Text Provider</Label>
                        <Select
                            value={settings.sttProvider}
                            onValueChange={(value: "browser" | "openai" | "azure") => {
                                // Update both provider and engine based on selection
                                updateSetting("sttProvider", value);
                                updateSetting("engineSTT", value === "browser" ? "browser" : "external");
                            }}
                            disabled={!settings.speechToText}
                        >
                            <SelectTrigger className="w-44">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="browser">Browser (Free)</SelectItem>
                                {sttProviders?.openai && <SelectItem value="openai">OpenAI Whisper</SelectItem>}
                                {sttProviders?.azure && <SelectItem value="azure">Azure Speech</SelectItem>}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* STT Configuration Warning - Only show for External API */}
                    {settings.speechToText && settings.sttProvider !== "browser" && sttConfigured === false && (
                        <div className="rounded-md border border-[var(--color-warning-w40)] bg-[var(--color-warning-w20)] p-3 dark:border-[var(--color-warning-w80)] dark:bg-[var(--color-warning-w95)]">
                            <div className="flex gap-2">
                                <AlertCircle className="mt-0.5 size-5 flex-shrink-0 text-[var(--color-warning-wMain)]" />
                                <div className="flex-1 text-sm">
                                    <p className="mb-1 font-semibold text-[var(--color-warning-w80)] dark:text-[var(--color-warning-w30)]">External STT Not Configured</p>
                                    <p className="mb-2 text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">
                                        To use External API mode, add configuration to your <code className="rounded bg-[var(--color-warning-w30)] px-1 py-0.5 text-xs dark:bg-[var(--color-warning-w90)]">webui.yaml</code>:
                                    </p>
                                    <div className="space-y-2">
                                        <div>
                                            <p className="mb-1 text-xs font-semibold text-[var(--color-warning-w80)] dark:text-[var(--color-warning-w30)]">OpenAI Whisper:</p>
                                            <pre className="overflow-x-auto rounded bg-[var(--color-warning-w30)] p-2 text-xs dark:bg-[var(--color-warning-w90)]">
                                                {`speech:
  stt:
    provider: openai
    openai:
      url: https://api.openai.com/v1/audio/transcriptions
      api_key: \${OPENAI_API_KEY}
      model: whisper-1`}
                                            </pre>
                                        </div>
                                        <div>
                                            <p className="mb-1 text-xs font-semibold text-[var(--color-warning-w80)] dark:text-[var(--color-warning-w30)]">Azure Speech:</p>
                                            <pre className="overflow-x-auto rounded bg-[var(--color-warning-w30)] p-2 text-xs dark:bg-[var(--color-warning-w90)]">
                                                {`speech:
  stt:
    provider: azure
    azure:
      api_key: \${AZURE_SPEECH_KEY}
      region: eastus
      language: en-US`}
                                            </pre>
                                        </div>
                                    </div>
                                    <p className="mt-2 text-xs text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">Or use Browser mode (free, no setup required).</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Language */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Language</Label>
                        <Select value={settings.languageSTT} onValueChange={value => updateSetting("languageSTT", value)} disabled={!settings.speechToText}>
                            <SelectTrigger className="w-44">
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
                </div>
            )}

            {/* Text-to-Speech Section */}
            {ttsEnabled && (
                <div className="space-y-4">
                    <div className="flex items-center gap-2 border-b pb-2">
                        <Volume2 className="size-5" />
                        <h3 className="text-lg font-semibold">Text-to-Speech</h3>
                    </div>

                    {/* Enable TTS */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Enable Text-to-Speech</Label>
                        <Switch checked={settings.textToSpeech} onCheckedChange={checked => updateSetting("textToSpeech", checked)} />
                    </div>

                    {/* TTS Provider */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Text-to-Speech Provider</Label>
                        <Select
                            value={settings.ttsProvider}
                            onValueChange={(value: "browser" | "gemini" | "azure" | "polly") => {
                                // Update both provider and engine based on selection
                                updateSetting("ttsProvider", value);
                                updateSetting("engineTTS", value === "browser" ? "browser" : "external");
                            }}
                            disabled={!settings.textToSpeech}
                        >
                            <SelectTrigger className="w-44">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="browser">Browser (Free)</SelectItem>
                                {ttsProviders?.gemini && <SelectItem value="gemini">Google Gemini</SelectItem>}
                                {ttsProviders?.azure && <SelectItem value="azure">Azure Neural</SelectItem>}
                                {ttsProviders?.polly && <SelectItem value="polly">AWS Polly</SelectItem>}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* TTS Configuration Warning - Only show for External API */}
                    {settings.textToSpeech && settings.ttsProvider !== "browser" && ttsConfigured === false && (
                        <div className="rounded-md border border-[var(--color-warning-w40)] bg-[var(--color-warning-w20)] p-3 dark:border-[var(--color-warning-w80)] dark:bg-[var(--color-warning-w95)]">
                            <div className="flex gap-2">
                                <AlertCircle className="mt-0.5 size-5 flex-shrink-0 text-[var(--color-warning-wMain)]" />
                                <div className="flex-1 text-sm">
                                    <p className="mb-1 font-semibold text-[var(--color-warning-w80)] dark:text-[var(--color-warning-w30)]">External TTS Not Configured</p>
                                    <p className="mb-2 text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">
                                        To use External API mode, configure TTS in your <code className="rounded bg-[var(--color-warning-w30)] px-1 py-0.5 text-xs dark:bg-[var(--color-warning-w90)]">webui.yaml</code>. Example for Gemini:
                                    </p>
                                    <pre className="overflow-x-auto rounded bg-[var(--color-warning-w30)] p-2 text-xs dark:bg-[var(--color-warning-w90)]">
                                        {`speech:
  tts:
    provider: gemini
    api_key: \${GEMINI_API_KEY}
    model: gemini-2.0-flash-exp`}
                                    </pre>
                                    <p className="mt-2 text-xs text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">Or use Browser mode (free, no setup required).</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TTS Configuration Warning for Polly - Only show for External API */}
                    {settings.textToSpeech && settings.ttsProvider === "polly" && ttsConfigured === false && (
                        <div className="rounded-md border border-[var(--color-warning-w40)] bg-[var(--color-warning-w20)] p-3 dark:border-[var(--color-warning-w80)] dark:bg-[var(--color-warning-w95)]">
                            <div className="flex gap-2">
                                <AlertCircle className="mt-0.5 size-5 flex-shrink-0 text-[var(--color-warning-wMain)]" />
                                <div className="flex-1 text-sm">
                                    <p className="mb-1 font-semibold text-[var(--color-warning-w80)] dark:text-[var(--color-warning-w30)]">External TTS Not Configured</p>
                                    <p className="mb-2 text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">
                                        To use AWS Polly, configure TTS in your <code className="rounded bg-[var(--color-warning-w30)] px-1 py-0.5 text-xs dark:bg-[var(--color-warning-w90)]">webui.yaml</code>:
                                    </p>
                                    <pre className="overflow-x-auto rounded bg-[var(--color-warning-w30)] p-2 text-xs dark:bg-[var(--color-warning-w90)]">
                                        {`speech:
  tts:
    provider: polly
    polly:
      aws_access_key_id: \${AWS_ACCESS_KEY_ID}
      aws_secret_access_key: \${AWS_SECRET_ACCESS_KEY}
      region: us-east-1
      engine: neural  # or 'standard'
      default_voice: Joanna`}
                                    </pre>
                                    <p className="mt-2 text-xs text-[var(--color-warning-w70)] dark:text-[var(--color-warning-w40)]">Or use Browser mode (free, no setup required).</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Voice Selection - Only show for External API */}
                    {settings.ttsProvider !== "browser" && (
                        <div className="flex items-center justify-between">
                            <Label className="font-medium">Voice</Label>
                            <div className="flex items-center gap-2">
                                <Select value={settings.voice} onValueChange={value => updateSetting("voice", value)} disabled={!settings.textToSpeech || loadingVoices}>
                                    <SelectTrigger className="w-[112px]">
                                        <SelectValue>{loadingVoices ? "Loading..." : settings.voice || "Select voice"}</SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        {availableVoices.length > 0 ? (
                                            // External mode - show loaded voices with grouping for Azure
                                            (() => {
                                                // Check if this is Azure provider (voices contain DragonHD)
                                                const isAzure = availableVoices.some(v => v.includes("DragonHD"));

                                                if (isAzure && settings.ttsProvider === "azure") {
                                                    // Group Azure voices into HD and Normal
                                                    const hdVoices = availableVoices.filter(v => v.includes("DragonHD"));
                                                    const normalVoices = availableVoices.filter(v => !v.includes("DragonHD"));

                                                    return (
                                                        <>
                                                            {hdVoices.length > 0 && (
                                                                <>
                                                                    <div className="text-muted-foreground px-2 py-1.5 text-xs font-semibold">HD Voices (Premium)</div>
                                                                    {hdVoices.map(voice => {
                                                                        // Format: "en-US-AvaMultilingualNeural:DragonHDLatestNeural" -> "Ava"
                                                                        const parts = voice.split("-");
                                                                        const lastPart = parts[parts.length - 1] || voice;
                                                                        const name = lastPart.replace("MultilingualNeural:DragonHDLatestNeural", "").replace("Neural:DragonHDLatestNeural", "").replace(":DragonHDLatestNeural", "");
                                                                        return (
                                                                            <SelectItem key={voice} value={voice}>
                                                                                {name}
                                                                            </SelectItem>
                                                                        );
                                                                    })}
                                                                </>
                                                            )}
                                                            {normalVoices.length > 0 && (
                                                                <>
                                                                    <div className="text-muted-foreground mt-1 border-t px-2 py-1.5 pt-2 text-xs font-semibold">Standard Voices</div>
                                                                    {normalVoices.map(voice => {
                                                                        // Format: "en-US-AvaMultilingualNeural" -> "Ava"
                                                                        const parts = voice.split("-");
                                                                        const lastPart = parts[parts.length - 1] || voice;
                                                                        const name = lastPart.replace("MultilingualNeural", "").replace("Neural", "");
                                                                        return (
                                                                            <SelectItem key={voice} value={voice}>
                                                                                {name}
                                                                            </SelectItem>
                                                                        );
                                                                    })}
                                                                </>
                                                            )}
                                                        </>
                                                    );
                                                } else {
                                                    return availableVoices.map(voice => {
                                                        // For Gemini voices like "Kore" or "Puck", show as-is
                                                        // For other formats, try to extract readable name
                                                        let displayName = voice;
                                                        if (voice.includes("-")) {
                                                            const parts = voice.split("-");
                                                            displayName = parts[parts.length - 1].replace("Neural", "").replace("Multilingual", "") || voice;
                                                        }
                                                        return (
                                                            <SelectItem key={voice} value={voice}>
                                                                {displayName}
                                                            </SelectItem>
                                                        );
                                                    });
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
                                <Button
                                    variant={playingSample ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => {
                                        if (!playingSample && !loadingSample) {
                                            playVoiceSample(settings.voice);
                                        }
                                    }}
                                    disabled={!settings.textToSpeech || !settings.voice || loadingVoices || playingSample || loadingSample}
                                    title={loadingSample ? "Loading sample..." : playingSample ? "Playing sample..." : "Play voice sample"}
                                    className="w-10 px-3"
                                >
                                    {loadingSample ? <Loader2 className="size-4 animate-spin" /> : playingSample ? <Volume2 className="size-4" /> : <Play className="size-4" />}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Playback Rate */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Playback Speed</Label>
                        <Input type="number" min={0.5} max={2.0} step={0.1} value={settings.playbackRate} onChange={e => updateSetting("playbackRate", parseFloat(e.target.value) || 1.0)} disabled={!settings.textToSpeech} className="w-44" />
                    </div>
                </div>
            )}
        </div>
    );
};
