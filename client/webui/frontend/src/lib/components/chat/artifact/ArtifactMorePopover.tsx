import React from "react";

import { Eye, EyeOff, RefreshCcw, Trash } from "lucide-react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";

interface ArtifactMorePopoverProps {
    children: React.ReactNode;
    hideDeleteAll?: boolean;
    showWorkingArtifacts?: boolean;
    onToggleWorkingArtifacts?: () => void;
    workingArtifactCount?: number;
}

export const ArtifactMorePopover: React.FC<ArtifactMorePopoverProps> = ({
    children,
    hideDeleteAll = false,
    showWorkingArtifacts = false,
    onToggleWorkingArtifacts,
    workingArtifactCount = 0,
}) => {
    const { artifactsRefetch, setIsBatchDeleteModalOpen } = useChatContext();

    const menuActions: MenuAction[] = [];

    // Add working artifacts toggle if callback is provided
    if (onToggleWorkingArtifacts) {
        const countLabel = workingArtifactCount > 0 ? ` (${workingArtifactCount})` : "";
        menuActions.push({
            id: "toggleWorking",
            label: showWorkingArtifacts
                ? `Hide Working Files${countLabel}`
                : `Show Working Files${countLabel}`,
            onClick: onToggleWorkingArtifacts,
            icon: showWorkingArtifacts ? <EyeOff /> : <Eye />,
            iconPosition: "left",
        });
    }

    menuActions.push({
        id: "refreshAll",
        label: "Refresh",
        onClick: () => {
            artifactsRefetch();
        },
        icon: <RefreshCcw />,
        iconPosition: "left",
        divider: onToggleWorkingArtifacts ? true : false,
    });

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
