import React from "react";

import { Eye, EyeOff, RefreshCcw, Trash } from "lucide-react";

import { Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";

interface ArtifactMorePopoverProps {
    children: React.ReactNode;
    hideDeleteAll?: boolean;
    showInternalArtifacts?: boolean;
    onToggleInternalArtifacts?: () => void;
    internalArtifactCount?: number;
}

export const ArtifactMorePopover: React.FC<ArtifactMorePopoverProps> = ({
    children,
    hideDeleteAll = false,
    showInternalArtifacts = false,
    onToggleInternalArtifacts,
    internalArtifactCount = 0,
}) => {
    const { artifactsRefetch, setIsBatchDeleteModalOpen } = useChatContext();

    const menuActions: MenuAction[] = [];

    // Add internal artifacts toggle if callback is provided
    if (onToggleInternalArtifacts) {
        const countLabel = internalArtifactCount > 0 ? ` (${internalArtifactCount})` : "";
        menuActions.push({
            id: "toggleInternal",
            label: showInternalArtifacts
                ? `Hide Internal Files${countLabel}`
                : `Show Internal Files${countLabel}`,
            onClick: onToggleInternalArtifacts,
            icon: showInternalArtifacts ? <EyeOff /> : <Eye />,
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
        divider: onToggleInternalArtifacts ? true : false,
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
