import React from "react";
import { SunMoon } from "lucide-react";
import { Switch } from "@/lib/components/ui";
import { useThemeContext, useConfigContext } from "@/lib/hooks";
import { SpeechSettingsPanel } from "./SpeechSettings";

export const AccountSettings: React.FC = () => {
    const { currentTheme, toggleTheme } = useThemeContext();
    const { configFeatureEnablement } = useConfigContext();

    const sttEnabled = configFeatureEnablement?.speechToText ?? true;
    const ttsEnabled = configFeatureEnablement?.textToSpeech ?? true;
    const speechEnabled = sttEnabled || ttsEnabled;

    return (
        <div className="space-y-10">
            {/* Dark Mode Section */}
            <div className="space-y-4">
                <div className="flex items-center justify-between border-b pb-2">
                    <div className="flex items-center gap-2">
                        <SunMoon className="size-5" />
                        <h3 className="text-lg font-semibold">Dark Mode Display</h3>
                    </div>
                    <Switch checked={currentTheme === "dark"} onCheckedChange={toggleTheme} />
                </div>
            </div>

            {/* Speech Settings - Only show if speech features are enabled */}
            {speechEnabled && <SpeechSettingsPanel />}
        </div>
    );
};
