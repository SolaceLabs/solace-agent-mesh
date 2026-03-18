import React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { navButtonStyles, iconWrapperStyles, iconStyles, navTextStyles } from "./navigationStyles";
import type { NavItem } from "./types";

export interface NavItemButtonProps {
    item: NavItem;
    isActive: boolean;
    onClick: () => void;
    isExpanded?: boolean;
    onToggleExpand?: () => void;
    className?: string;
    indent?: boolean;
    hasActiveChild?: boolean;
    isCollapsed?: boolean;
}

export const NavItemButton: React.FC<NavItemButtonProps> = ({ item, isActive, onClick, isExpanded, onToggleExpand, className, indent, hasActiveChild, isCollapsed = false }) => {
    const isHighlighted = isActive || hasActiveChild;

    return (
        <button onClick={item.hasSubmenu ? onToggleExpand : onClick} className={cn(navButtonStyles({ indent: !!indent, active: !!indent && isActive }), className)}>
            {indent ? (
                <span className={navTextStyles({ active: isActive })}>{item.label}</span>
            ) : (
                <>
                    <div className={iconWrapperStyles({ active: isHighlighted, withMargin: true })}>
                        <item.icon className={iconStyles({ active: isHighlighted })} />
                    </div>
                    <span className={cn(navTextStyles({ active: isActive }), "overflow-hidden whitespace-nowrap transition-[opacity,max-width] duration-200", isCollapsed ? "max-w-0 opacity-0" : "max-w-[180px] opacity-100")}>{item.label}</span>
                </>
            )}
            {!isCollapsed && item.hasSubmenu && <span className="ml-auto text-(--darkSurface-text)">{isExpanded ? <ChevronUp className="size-6" /> : <ChevronDown className="size-6" />}</span>}
            {!isCollapsed && item.badge}
        </button>
    );
};
