import { Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";
import { useThemeContext } from "@/lib/hooks/useThemeContext";

interface SettingsPopoverProps {
    children: ReactNode;
}

export function SettingsPopover({ children }: SettingsPopoverProps) {
    const { currentTheme, toggleTheme } = useThemeContext();

    const menuActions: MenuAction[] = [
        {
            id: "toggle-theme",
            label: "Toggle theme",
            icon: currentTheme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />,
            onClick: () => {
                toggleTheme();
            },
        },
    ];

    return (
        <Popover>
            <PopoverTrigger asChild>{children}</PopoverTrigger>
            <PopoverContent align="end" side="right" className="bg-background min-w-[200px] p-1" sideOffset={0}>
                <Menu actions={menuActions} />
            </PopoverContent>
        </Popover>
    );
}
