import { SunMoon } from "lucide-react";

import { useThemeContext } from "@/lib/hooks";
import { Button } from "@/lib/components/ui";

export const ToggleThemeButton: React.FC = () => {
    const { currentTheme, toggleTheme } = useThemeContext();
    const label = `Toggle theme (currently ${currentTheme})`;

    return (
        <Button variant="ghost" onClick={toggleTheme} className="h-10 w-10 p-2" tooltip={label} aria-label={label}>
            <SunMoon className="size-5" />
        </Button>
    );
};
