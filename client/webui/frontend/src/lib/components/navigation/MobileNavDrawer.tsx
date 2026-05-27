import React from "react";

import { Sheet, SheetContent, SheetTitle } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

export interface MobileNavItem {
    id: string;
    label: string;
    icon: React.ElementType;
    onClick: () => void;
    isActive?: boolean;
}

interface MobileNavDrawerProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    items: MobileNavItem[];
    bottomItems?: MobileNavItem[];
}

export const MobileNavDrawer: React.FC<MobileNavDrawerProps> = ({ open, onOpenChange, items, bottomItems }) => {
    const renderItem = (item: MobileNavItem) => {
        const Icon = item.icon;
        return (
            <button
                key={item.id}
                type="button"
                onClick={() => {
                    item.onClick();
                    onOpenChange(false);
                }}
                className={cn(
                    "flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm transition-colors",
                    "text-(--darkSurface-text) hover:bg-(--darkSurface-bgHover)",
                    item.isActive && "bg-(--darkSurface-bgHover) text-(--darkSurface-brandMain)"
                )}
                aria-current={item.isActive ? "page" : undefined}
            >
                <Icon className={cn("size-5 shrink-0", item.isActive && "text-(--darkSurface-brandMain)")} />
                <span className="truncate">{item.label}</span>
            </button>
        );
    };

    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent side="left" className="w-[80vw] max-w-xs border-r-(--darkSurface-border) bg-(--darkSurface-bg) p-0">
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <div className="flex h-full flex-col">
                    <div className="flex-1 space-y-1 overflow-y-auto p-2 pt-12">{items.map(renderItem)}</div>
                    {bottomItems && bottomItems.length > 0 && <div className="space-y-1 border-t border-(--darkSurface-border) p-2">{bottomItems.map(renderItem)}</div>}
                </div>
            </SheetContent>
        </Sheet>
    );
};
