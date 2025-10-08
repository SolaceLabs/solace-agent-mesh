import React from "react";

import { CheckIcon } from "lucide-react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";

export const SortOption = {
    NameAsc: "name_asc",
    NameDesc: "name_desc",
    DateAsc: "date_asc",
    DateDesc: "date_desc",
} as const;

export type SortOptionType = (typeof SortOption)[keyof typeof SortOption];

const getSortOptionLabel = (option: SortOptionType): string => {
    switch (option) {
        case SortOption.NameAsc:
            return "Name (A-Z)";
        case SortOption.NameDesc:
            return "Name (Z-A)";
        case SortOption.DateAsc:
            return "Date (oldest first)";
        case SortOption.DateDesc:
            return "Date (newest first)";
    }
};

interface SortPopoverProps {
    currentSortOption: SortOptionType;
    onSortChange: (option: SortOptionType) => void;
    children: React.ReactNode;
}

export const SortPopover: React.FC<SortPopoverProps> = ({ currentSortOption, onSortChange, children }) => {
    const menuActions: MenuAction[] = Object.values(SortOption).map(option => ({
        id: option,
        label: getSortOptionLabel(option as SortOptionType),
        onClick: () => onSortChange(option as SortOptionType),
        icon: currentSortOption === option ? <CheckIcon /> : undefined,
        iconPosition: "right",
    }));

    return (
        <Popover>
            <PopoverTrigger asChild>{children}</PopoverTrigger>
            <PopoverContent align="end" side="bottom" className="w-auto" sideOffset={0}>
                <Menu actions={menuActions} />
            </PopoverContent>
        </Popover>
    );
};
