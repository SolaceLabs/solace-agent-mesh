import React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { cn } from "@/lib/utils";
import type { NavItemConfig } from "@/lib/types/fe";
import { navButtonStyles, iconWrapperStyles, iconStyles, navTextStyles } from "./navigationStyles";

type NavItem = NavItemConfig & { hasSubmenu?: boolean };

export interface NavItemButtonProps {
    item: NavItem;
    isActive: boolean;
    onClick: () => void;
    isExpanded?: boolean;
    onToggleExpand?: () => void;
    className?: string;
    indent?: boolean;
    hasActiveChild?: boolean;
}

export const NavItemButton: React.FC<NavItemButtonProps> = ({ item, isActive, onClick, isExpanded, onToggleExpand, className, indent, hasActiveChild }) => {
    const isHighlighted = isActive || hasActiveChild;

    const buttonContent = (
        <button onClick={item.hasSubmenu ? onToggleExpand : onClick} className={cn(navButtonStyles({ indent: !!indent, active: !!indent && isActive }), className)}>
            {indent ? (
                <span className={navTextStyles({ active: isActive })}>{item.label}</span>
            ) : (
                <>
                    <div className={iconWrapperStyles({ active: isHighlighted, withMargin: true })}>
                        <item.icon className={iconStyles({ active: isHighlighted })} />
                    </div>
                    <span className={navTextStyles({ active: isHighlighted })}>{item.label}</span>
                </>
            )}
            {item.hasSubmenu && <span className="ml-auto text-[var(--color-primary-text-w10)]">{isExpanded ? <ChevronUp className="size-6" /> : <ChevronDown className="size-6" />}</span>}
            {item.badge}
        </button>
    );

    if (item.tooltip) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
                <TooltipContent side="right">
                    <p>{item.tooltip}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

    return buttonContent;
};
