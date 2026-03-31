import React from "react";

import { cn } from "@/lib/utils";
import type { NavigationItem } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";
import { LifecycleBadge } from "@/lib/components/ui/lifecycleBadge";

interface NavigationItemProps {
    item: NavigationItem;
    isActive: boolean;
    onItemClick?: (itemId: string) => void;
}

export const NavigationButton: React.FC<NavigationItemProps> = ({ item, isActive, onItemClick }) => {
    const { id, label, icon: Icon, disabled, badge } = item;

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
        <Tooltip>
            <TooltipTrigger asChild>
                <button
                    type="button"
                    onClick={onItemClick ? handleClick : undefined}
                    onKeyDown={onItemClick ? handleKeyDown : undefined}
                    disabled={disabled}
                    className={cn(
                        "relative mx-auto flex w-full cursor-pointer flex-col items-center px-3 py-5 text-xs transition-colors",
                        "bg-(--darkSurface-bg) hover:bg-(--darkSurface-bgHover)",
                        "text-(--darkSurface-text) hover:bg-(--darkSurface-bgHover) hover:text-(--darkSurface-text)",
                        "border-l-4 border-(--darkSurface-bg)",
                        isActive ? "border-l-4 border-(--darkSurface-brandMain) bg-(--darkSurface-bgHover)/50" : ""
                    )}
                    aria-label={label}
                    aria-current={isActive ? "page" : undefined}
                >
                    <Icon className={cn("mb-1 h-6 w-6", isActive && "text-(--darkSurface-brandMain)")} />
                    <span className="text-center text-[13px] leading-tight">{label}</span>
                    {badge && <LifecycleBadge className="mt-1 text-[9px]">{badge}</LifecycleBadge>}
                </button>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
    );
};
