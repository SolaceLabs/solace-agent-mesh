import React, { useState } from "react";
import { SunMoon, Activity } from "lucide-react";
import { useThemeContext } from "@/lib/hooks";
import { Label, Switch } from "@/lib/components/ui";

const CONTEXT_INDICATOR_STORAGE_KEY = "show-context-indicator";

export const GeneralSettings: React.FC = () => {
    const { currentTheme, toggleTheme } = useThemeContext();
    const [showContextIndicator, setShowContextIndicator] = useState(() => {
        const saved = localStorage.getItem(CONTEXT_INDICATOR_STORAGE_KEY);
        return saved !== null ? saved === "true" : true; // Default to true (shown)
    });

    const handleContextIndicatorToggle = (checked: boolean) => {
        setShowContextIndicator(checked);
        localStorage.setItem(CONTEXT_INDICATOR_STORAGE_KEY, String(checked));
        // Dispatch event to notify ChatPage of the change
        window.dispatchEvent(new CustomEvent("context-indicator-visibility-changed", { detail: { visible: checked } }));
    };

    return (
        <div className="space-y-6">
            {/* Display Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Display</h3>
                </div>

                {/* Theme Toggle */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SunMoon className="size-4" />
                        <Label className="font-medium">Dark Mode</Label>
                    </div>
                    <Switch checked={currentTheme === "dark"} onCheckedChange={toggleTheme} />
                </div>

                {/* Context Indicator Toggle */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Activity className="size-4" />
                        <Label className="font-medium">Show Context Usage Indicator</Label>
                    </div>
                    <Switch checked={showContextIndicator} onCheckedChange={handleContextIndicatorToggle} />
                </div>
            </div>
        </div>
    );
};
