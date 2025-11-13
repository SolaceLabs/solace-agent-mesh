import React from "react";
import { Type } from "lucide-react";
import { useAudioSettings } from "@/lib/hooks";
import { Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";

export const GeneralSettings: React.FC = () => {
    const { settings, updateSetting } = useAudioSettings();

    return (
        <div className="space-y-6">
            {/* Font Size Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2">
                    <Type className="size-5" />
                    <h3 className="text-lg font-semibold">Display</h3>
                </div>

                {/* Font Size Control */}
                <div className="space-y-2">
                    <Label>
                        <span className="font-medium">Font Size</span>
                        <span className="text-sm text-muted-foreground ml-2">
                            Adjust the UI text size
                        </span>
                    </Label>
                    <Select
                        value={settings.fontSize || "medium"}
                        onValueChange={(value: "small" | "medium" | "large" | "extra-large") => updateSetting("fontSize", value)}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select font size" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="small">Small (14px)</SelectItem>
                            <SelectItem value="medium">Medium (16px)</SelectItem>
                            <SelectItem value="large">Large (18px)</SelectItem>
                            <SelectItem value="extra-large">Extra Large (20px)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
};