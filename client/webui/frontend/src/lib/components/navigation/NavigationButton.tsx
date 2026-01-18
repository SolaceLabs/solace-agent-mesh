import React from "react";

import { cn } from "@/lib/utils";
import type { NavigationItem } from "@/lib/types";

interface NavigationItemProps {
    item: NavigationItem;
    isActive: boolean;
    onItemClick?: (itemId: string) => void;
}

export const NavigationButton: React.FC<NavigationItemProps> = ({ item, isActive, onItemClick }) => {
    const { id, label, icon: Icon, disabled } = item;

    const handleClick = () => {
        if (!disabled && onItemClick) {
            onItemClick(id);
        }
    };

    const handleKeyDown = (event: React.KeyboardEvent) => {
        if (event.key === "Enter" || event.key === " ") {
            handleClick();
        }
    };

    return (
                <button
                    type="button"
                    onClick={onItemClick ? handleClick : undefined}
                    onKeyDown={onItemClick ? handleKeyDown : undefined}
                    disabled={disabled}
                    className={cn(
                        "relative mx-auto flex w-full cursor-pointer flex-col items-center px-3 pt-3 text-xs transition-colors",
                        "hover:bg-(--color-background-w10)",
                        "text-(--color-brand-wMain)",
                        isActive ? "border-b-4 border-(--color-brand-wMain)" : ""
                    )}
                    aria-label={label}
                    aria-current={isActive ? "page" : undefined}
                >
                    <Icon className={cn("mb-1 h-6 w-6", isActive && "text-(--color-brand-wMain)")} />
                    <span className="text-center text-[13px] leading-tight">{label}</span>
                    {/* {badge && (
                        <Badge variant="outline" className="mt-1 h-4 bg-(--color-secondary-w80) pt-1 text-[8px] leading-none text-(--color-secondary-text-w10) uppercase">
                            {badge}
                        </Badge>
                    )} */}
                </button>
    );
};
