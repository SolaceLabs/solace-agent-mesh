import React from "react";

import { Trash } from "lucide-react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";

interface MorePopoverProps {
    children: React.ReactNode;
}

export const MorePopover: React.FC<MorePopoverProps> = ({ children }) => {
	const { setIsBatchDeleteModalOpen } = useChatContext();

    const menuActions: MenuAction[] = [{
        id: "deleteAll",
        label: "Delete All",
        onClick: () => { setIsBatchDeleteModalOpen(true); },
        icon: <Trash />,
        iconPosition: "right",
    }];

    return (
        <Popover>
            <PopoverTrigger asChild>{children}</PopoverTrigger>
            <PopoverContent align="end" side="bottom" className="bg-background min-w-[200px] p-1" sideOffset={0}>
                <Menu actions={menuActions} />
            </PopoverContent>
        </Popover>
    );
};
