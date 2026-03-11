import { SunMoon } from "lucide-react";

import { useThemeContext } from "@/lib/hooks";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";

export const ToggleThemeButton: React.FC = () => {
    const { currentTheme, themes, toggleTheme } = useThemeContext();
    const currentLabel = themes.find(t => t.id === currentTheme)?.label ?? currentTheme;
    const label = `Toggle theme (${currentLabel})`;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <button
                    type="button"
                    onClick={toggleTheme}
                    className="relative mx-auto flex w-full cursor-pointer flex-col items-center bg-(--primary-w100) px-3 py-5 text-xs text-(--primary-text-w10) transition-colors hover:bg-(--primary-w90) hover:text-(--primary-text-w10) disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={label}
                    title={label}
                >
                    <SunMoon className="mb-1 h-6 w-6" />
                </button>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
    );
};
