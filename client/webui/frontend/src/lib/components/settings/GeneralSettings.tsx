import React from "react";
import { Palette } from "lucide-react";
import { useThemeContext } from "@/lib/hooks";
import { Label } from "@/lib/components/ui";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";

export const GeneralSettings: React.FC = () => {
    const { currentTheme, themes, setTheme } = useThemeContext();

    return (
        <div className="space-y-6">
            {/* Display Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Display</h3>
                </div>

                {/* Theme Selector */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Palette className="size-4" />
                        <Label className="font-medium">Theme</Label>
                    </div>
                    <Select value={currentTheme} onValueChange={setTheme}>
                        <SelectTrigger className="w-40">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {themes.map(t => (
                                <SelectItem key={t.id} value={t.id}>
                                    {t.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
};
