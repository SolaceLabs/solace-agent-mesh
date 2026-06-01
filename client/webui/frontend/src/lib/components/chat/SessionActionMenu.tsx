import React from "react";
import { Trash2, Pencil, FolderInput, MoreHorizontal, PanelsTopLeft, Sparkles, Share2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/lib/components/ui";
import { useChatSurface } from "@/lib/hooks";
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
    const surface = useChatSurface();
    // Which items appear is driven by the surface allowlist (in canonical order),
    // so a new action is added once here — there's no separate per-surface branch to keep in sync.
    const allows = surface.sessionActions;

    const showGoToProject = allows.includes("goToProject") && !!session.projectId && !!onGoToProject;
    const showShare = allows.includes("share") && !!onShare;

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className={cn("h-8 w-8 p-0", triggerClassName)} onClick={e => e.stopPropagation()}>
                    <MoreHorizontal size={16} />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
                {showGoToProject && (
                    <>
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onGoToProject?.(session);
                            }}
                        >
                            <PanelsTopLeft size={16} className="mr-2" />
                            Go to Project
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                    </>
                )}
                {allows.includes("rename") && (
                    <DropdownMenuItem
                        onClick={e => {
                            e.stopPropagation();
                            onRename(session);
                        }}
                    >
                        <Pencil size={16} className="mr-2" />
                        Rename
                    </DropdownMenuItem>
                )}
                {allows.includes("renameWithAI") && (
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
                )}
                {allows.includes("move") && (
                    <DropdownMenuItem
                        onClick={e => {
                            e.stopPropagation();
                            onMove(session);
                        }}
                    >
                        <FolderInput size={16} className="mr-2" />
                        Move to Project
                    </DropdownMenuItem>
                )}
                {showShare && (
                    <DropdownMenuItem
                        onClick={e => {
                            e.stopPropagation();
                            onShare?.(session);
                        }}
                    >
                        <Share2 size={16} className="mr-2" />
                        Share
                    </DropdownMenuItem>
                )}
                {allows.includes("delete") && (
                    <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={e => {
                                e.stopPropagation();
                                onDelete(session);
                            }}
                        >
                            <Trash2 size={16} className="mr-2" />
                            Delete
                        </DropdownMenuItem>
                    </>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
};
