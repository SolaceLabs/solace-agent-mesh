import React from "react";
import { X, NotepadText, Tag, Calendar, Pencil, History, Trash2, User, MoreHorizontal, SquarePen, Download } from "lucide-react";
import type { PromptGroup } from "@/lib/types/prompts";
import { formatPromptDate } from "@/lib/utils/promptUtils";
import { Button, Tooltip, TooltipContent, TooltipTrigger, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useConfigContext } from "@/lib/hooks";

interface PromptDetailSidePanelProps {
    prompt: PromptGroup | null;
    onClose: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
    onExport?: (prompt: PromptGroup) => void;
}

export const PromptDetailSidePanel: React.FC<PromptDetailSidePanelProps> = ({ prompt, onClose, onEdit, onDelete, onViewVersions, onUseInChat, onExport }) => {
    const { configFeatureEnablement } = useConfigContext();
    const versionHistoryEnabled = configFeatureEnablement?.promptVersionHistory ?? true;
    const showVersionHistory = versionHistoryEnabled && onViewVersions;

    if (!prompt) return null;

    const handleEdit = () => {
        onEdit(prompt);
    };

    const handleDelete = () => {
        onDelete(prompt.id, prompt.name);
    };

    const handleViewVersions = () => {
        if (onViewVersions) {
            onViewVersions(prompt);
        }
    };

    const handleUseInChat = () => {
        if (onUseInChat) {
            onUseInChat(prompt);
        }
    };

    const handleExport = () => {
        if (onExport) {
            onExport(prompt);
        }
    };

    return (
        <div className="bg-background flex h-full w-full flex-col border-l">
            {/* Header */}
            <div className="border-b p-4">
                <div className="mb-2 flex items-center justify-between">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <NotepadText className="text-muted-foreground h-5 w-5 flex-shrink-0" />
                        <Tooltip delayDuration={300}>
                            <TooltipTrigger asChild>
                                <h2 className="cursor-default truncate text-lg font-semibold">{prompt.name}</h2>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">
                                <p>{prompt.name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                    <div className="ml-2 flex flex-shrink-0 items-center gap-1">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0" tooltip="Actions">
                                    <MoreHorizontal className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                {onExport && (
                                    <DropdownMenuItem onClick={handleExport}>
                                        <Download size={14} className="mr-2" />
                                        Export Prompt
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={handleEdit}>
                                    <Pencil size={14} className="mr-2" />
                                    Edit Prompt
                                </DropdownMenuItem>
                                {showVersionHistory && (
                                    <DropdownMenuItem onClick={handleViewVersions}>
                                        <History size={14} className="mr-2" />
                                        Open Version History
                                    </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={handleDelete}>
                                    <Trash2 size={14} className="mr-2" />
                                    Delete All Versions
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0" tooltip="Close">
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
                {prompt.category && (
                    <span className="bg-primary/10 text-primary inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium">
                        <Tag size={12} />
                        {prompt.category}
                    </span>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Description and Chat Shortcut - with background */}
                <div className="bg-muted/50 space-y-6 rounded p-4">
                    {/* Description */}
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Description</h3>
                        <div className="text-sm leading-relaxed">{prompt.description || "No description provided."}</div>
                    </div>

                    {/* Chat Shortcut */}
                    {prompt.command && (
                        <div>
                            <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Chat Shortcut</h3>
                            <div>
                                <span className="text-primary bg-primary/10 inline-block rounded px-2 py-0.5 font-mono text-xs">/{prompt.command}</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Use in New Chat Button */}
                {onUseInChat && (
                    <Button data-testid="startNewChatButton" onClick={handleUseInChat} className="w-full">
                        <SquarePen className="h-4 w-4" />
                        Use in New Chat
                    </Button>
                )}

                {/* Content - no background */}
                {prompt.productionPrompt && (
                    <div>
                        <h3 className="text-muted-foreground mb-2 text-xs font-semibold">Content</h3>
                        <div className="font-mono text-xs break-words whitespace-pre-wrap">
                            {prompt.productionPrompt.promptText.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                if (part.match(/\{\{[^}]+\}\}/)) {
                                    return (
                                        <span key={index} className="bg-primary/20 text-primary rounded px-1 font-medium">
                                            {part}
                                        </span>
                                    );
                                }
                                return <span key={index}>{part}</span>;
                            })}
                        </div>
                    </div>
                )}
            </div>

            {/* Metadata - Sticky at bottom */}
            <div className="bg-background space-y-2 border-t p-4">
                <div className="text-muted-foreground flex items-center gap-2 text-xs">
                    <User size={12} />
                    <span>Created by: {prompt.authorName || prompt.userId}</span>
                </div>
                {prompt.updatedAt && (
                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                        <Calendar size={12} />
                        <span>Last updated: {formatPromptDate(prompt.updatedAt)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};
