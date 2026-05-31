import React from "react";
import { Trash2, Pencil, FolderInput, MoreHorizontal, PanelsTopLeft, Sparkles, Share2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/lib/components/ui";
import { useConfigContext } from "@/lib/hooks";
import type { Session } from "@/lib/types";

export interface SessionActionMenuProps {
    session: Session;
    onRename: (session: Session) => void;
    onRenameWithAI: (session: Session) => void;
    onMove: (session: Session) => void;
    onDelete: (session: Session) => void;
    onGoToProject?: (session: Session) => void;
    onShare?: (session: Session) => void;
    isRegeneratingTitle?: boolean;
    /** Additional className for the trigger button (e.g., hover visibility) */
    triggerClassName?: string;
}

export const SessionActionMenu: React.FC<SessionActionMenuProps> = ({ session, onRename, onRenameWithAI, onMove, onDelete, onGoToProject, onShare, isRegeneratingTitle = false, triggerClassName }) => {
    const { agentMode } = useConfigContext();

    const renameItem = (
        <DropdownMenuItem
            onClick={e => {
                e.stopPropagation();
                onRename(session);
            }}
        >
            <Pencil size={16} className="mr-2" />
            Rename
        </DropdownMenuItem>
    );

    const renameWithAIItem = (
        <DropdownMenuItem
            onClick={e => {
                e.stopPropagation();
                onRenameWithAI(session);
            }}
            disabled={isRegeneratingTitle}
        >
            <Sparkles size={16} className={cn("mr-2", isRegeneratingTitle && "animate-pulse")} />
            Rename with AI
        </DropdownMenuItem>
    );

    const deleteItem = (
        <DropdownMenuItem
            onClick={e => {
                e.stopPropagation();
                onDelete(session);
            }}
        >
            <Trash2 size={16} className="mr-2" />
            Delete
        </DropdownMenuItem>
    );

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className={cn("h-8 w-8 p-0", triggerClassName)} onClick={e => e.stopPropagation()}>
                    <MoreHorizontal size={16} />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
                {agentMode ? (
                    // Agent Mode allowlist: only these actions are ever shown. New menu
                    // items added below must be added to the full-UI branch only.
                    <>
                        {renameItem}
                        {renameWithAIItem}
                        <DropdownMenuSeparator />
                        {deleteItem}
                    </>
                ) : (
                    <>
                        {session.projectId && onGoToProject && (
                            <>
                                <DropdownMenuItem
                                    onClick={e => {
                                        e.stopPropagation();
                                        onGoToProject(session);
                                    }}
                                >
                                    <PanelsTopLeft size={16} className="mr-2" />
                                    Go to Project
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                            </>
                        )}
                        {renameItem}
                        {renameWithAIItem}
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onMove(session);
                            }}
                        >
                            <FolderInput size={16} className="mr-2" />
                            Move to Project
                        </DropdownMenuItem>
                        {onShare && (
                            <DropdownMenuItem
                                onClick={e => {
                                    e.stopPropagation();
                                    onShare(session);
                                }}
                            >
                                <Share2 size={16} className="mr-2" />
                                Share
                            </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        {deleteItem}
                    </>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
};
