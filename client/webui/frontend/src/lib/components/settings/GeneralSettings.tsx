import React from "react";
import { Type, SunMoon } from "lucide-react";
import { useAudioSettings, useThemeContext } from "@/lib/hooks";
import { Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Switch } from "@/lib/components/ui";

export const GeneralSettings: React.FC = () => {
    const { settings, updateSetting } = useAudioSettings();
    const { currentTheme, toggleTheme } = useThemeContext();

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

                {/* Font Size Control */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Type className="size-4" />
                        <Label className="font-medium">Font Size</Label>
                    </div>
                    <Select value={settings.fontSize || "medium"} onValueChange={(value: "small" | "medium" | "large" | "extra-large") => updateSetting("fontSize", value)}>
                        <SelectTrigger className="w-40">
                            <SelectValue placeholder="Select font size" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="small">Small</SelectItem>
                            <SelectItem value="medium">Medium</SelectItem>
                            <SelectItem value="large">Large</SelectItem>
                            <SelectItem value="extra-large">Extra Large</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
};
