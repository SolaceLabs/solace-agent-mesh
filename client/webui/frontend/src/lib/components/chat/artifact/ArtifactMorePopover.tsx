import React from "react";

import { RefreshCcw, Trash } from "lucide-react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";

interface ArtifactMorePopoverProps {
    children: React.ReactNode;
    hideDeleteAll?: boolean;
}

export const ArtifactMorePopover: React.FC<ArtifactMorePopoverProps> = ({ children, hideDeleteAll = false }) => {
    const { artifactsRefetch, setIsBatchDeleteModalOpen } = useChatContext();

    const menuActions: MenuAction[] = [
        {
            id: "refreshAll",
            label: "Refresh",
            onClick: () => {
                artifactsRefetch();
            },
            icon: <RefreshCcw />,
            iconPosition: "left",
        },
    ];

    if (!hideDeleteAll) {
        menuActions.push({
            id: "deleteAll",
            label: "Delete All",
            onClick: () => {
                setIsBatchDeleteModalOpen(true);
            },
            icon: <Trash />,
            iconPosition: "left",
            divider: true,
        });
    }

    return (
        <Popover>
            <PopoverTrigger asChild>{children}</PopoverTrigger>
            <PopoverContent align="end" side="bottom" className="w-auto" sideOffset={0}>
                <Menu actions={menuActions} />
            </PopoverContent>
        </Popover>
    );
};
