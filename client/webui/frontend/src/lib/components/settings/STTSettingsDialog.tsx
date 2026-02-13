import React, { useState, useEffect } from "react";
import { Mic, AlertCircle } from "lucide-react";
import { useAudioSettings, useConfigContext } from "@/lib/hooks";
import { Label, Switch, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Dialog, DialogContent, DialogDescription, DialogTitle, VisuallyHidden } from "@/lib/components/ui";
import { api } from "@/lib/api";

interface STTSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export const STTSettingsDialog: React.FC<STTSettingsDialogProps> = ({ open, onOpenChange }) => {
    const { settings, updateSetting } = useAudioSettings();
    const { configFeatureEnablement } = useConfigContext();
    const [sttConfigured, setSttConfigured] = useState<boolean | null>(null);
    const [sttProviders, setSttProviders] = useState<{ openai: boolean; azure: boolean } | null>(null);

    // Feature flags
    const sttEnabled = configFeatureEnablement?.speechToText ?? true;

    // Check STT configuration status and auto-reset provider if needed
    useEffect(() => {
        if (!open) return;

        const checkConfig = async () => {
            try {
                const config = await api.webui.get("/api/v1/speech/config");
                const sttExt = config.sttExternal || false;

                setSttConfigured(sttExt);

                // Set per-provider status
                if (config.sttProviders) {
                    setSttProviders(config.sttProviders);
                }

                // Auto-reset provider to browser if external not configured
                if (!sttExt && settings.sttProvider !== "browser") {
                    console.warn("External STT not configured, resetting provider to browser");
                    updateSetting("sttProvider", "browser");
                    updateSetting("engineSTT", "browser");
                }
            } catch (error) {
                console.error("Error checking speech config:", error);
            }
        };
        checkConfig();
    }, [open, settings.sttProvider, updateSetting]);

    if (!sttEnabled) {
        return null;
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md" showCloseButton={true}>
                <VisuallyHidden>
                    <DialogTitle>Voice to Text Settings</DialogTitle>
                    <DialogDescription>Configure speech-to-text settings</DialogDescription>
                </VisuallyHidden>

                <div className="space-y-4">
                    <div className="flex items-center gap-2 border-b pb-2">
                        <Mic className="size-5" />
                        <h3 className="text-lg font-semibold">Voice to Text</h3>
                    </div>

                    {/* Enable STT */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Enable Speech-to-Text</Label>
                        <Switch checked={settings.speechToText} onCheckedChange={checked => updateSetting("speechToText", checked)} />
                    </div>

                    {/* STT Provider */}
                    <div className="flex items-center justify-between">
                        <Label className="font-medium">Provider</Label>
                        <Select
                            value={settings.sttProvider}
                            onValueChange={(value: "browser" | "openai" | "azure") => {
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
            </DialogContent>
        </Dialog>
    );
};
