import React from "react";
import { SunMoon } from "lucide-react";
import { useThemeContext } from "@/lib/hooks";
import { Label, Switch } from "@/lib/components/ui";

export const GeneralSettings: React.FC = () => {
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
            </div>
        </div>
    );
};
