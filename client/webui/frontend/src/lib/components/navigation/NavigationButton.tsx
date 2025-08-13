import React from "react";

import { cn } from "@/lib/utils";
import type { NavigationItem } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";

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
        <Tooltip>
            <TooltipTrigger asChild>
                <button
                    type="button"
                    onClick={onItemClick ? handleClick : undefined}
                    onKeyDown={onItemClick ? handleKeyDown : undefined}
                    disabled={disabled}
                    className={cn(
                        "relative mx-auto flex w-full cursor-pointer flex-col items-center border-l-4 border-[var(--color-primary-w100)] px-3 py-5 text-xs transition-colors",
                        "bg-[var(--color-primary-w100)] hover:bg-[var(--color-primary-w90)]",
                        "text-[var(--color-primary-text-w10)] hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)]",
                        "disabled:cursor-not-allowed disabled:opacity-50",
                        isActive ? "border-l-4 border-[var(--color-brand-wMain)] bg-[var(--color-primary-w90)]" : ""
                    )}
                    aria-label={label}
                    aria-current={isActive ? "page" : undefined}
                >
                    <Icon className={cn("mb-1 h-6 w-6", isActive && "text-[var(--color-brand-wMain)]")} />
                    <span className="text-center text-[13px] leading-tight">{label}</span>
                </button>
            </TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
    );
};
