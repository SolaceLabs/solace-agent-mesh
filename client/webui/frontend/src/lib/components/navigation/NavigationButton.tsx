import React from "react";

import { cn } from "@/lib/utils";
import type { NavigationItem } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";
import { Badge } from "@/lib/components/ui/badge";

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
                        "bg-(--color-primary-w100) hover:bg-(--color-primary-w90)",
                        "text-(--color-primary-text-w10) hover:bg-(--color-primary-w90) hover:text-(--color-background-w10)",
                        "border-l-4 border-(--color-primary-w100)",
                        isActive ? "border-l-4 border-(--color-brand-wMain) bg-(--color-primary-w90)" : ""
                    )}
                    aria-label={label}
                    aria-current={isActive ? "page" : undefined}
                >
                    <Icon className={cn("mb-1 h-6 w-6", isActive && "text-(--color-brand-wMain)")} />
                    <span className="text-center text-[13px] leading-tight">{label}</span>
                    {badge && (
                        <Badge variant="outline" className="mt-1 border-gray-400 bg-(--color-secondary-w80) px-1 py-0.5 text-[8px] leading-tight text-(--color-secondary-text-w10) uppercase">
                            {badge}
                        </Badge>
                    )}
                </button>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
    );
};
