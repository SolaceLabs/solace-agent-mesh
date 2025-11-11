import React from "react";
import { X, FileText, Tag, Calendar, Pencil, History, Trash2, User, MoreHorizontal, SquarePen } from "lucide-react";
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
}

export const PromptDetailSidePanel: React.FC<PromptDetailSidePanelProps> = ({
    prompt,
    onClose,
    onEdit,
    onDelete,
    onViewVersions,
    onUseInChat,
}) => {
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

    return (
        <div className="w-full h-full border-l bg-background flex flex-col">
            {/* Header */}
            <div className="p-4 border-b">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                        <FileText className="h-5 w-5 flex-shrink-0 text-muted-foreground" />
                        <Tooltip delayDuration={300}>
                            <TooltipTrigger asChild>
                                <h2 className="text-lg font-semibold truncate cursor-default">
                                    {prompt.name}
                                </h2>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">
                                <p>{prompt.name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0" tooltip="Actions">
                                    <MoreHorizontal className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
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
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={onClose}
                            className="h-8 w-8 p-0"
                            tooltip="Close"
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
                {prompt.category && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-primary/10 text-primary">
                        <Tag size={12} />
                        {prompt.category}
                    </span>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Description and Chat Shortcut - with background */}
                <div className="bg-muted/50 p-4 rounded space-y-6">
                    {/* Description */}
                    <div>
                        <h3 className="text-xs font-semibold text-muted-foreground mb-2">Description</h3>
                        <div className="text-sm leading-relaxed">
                            {prompt.description || "No description provided."}
                        </div>
                    </div>

                    {/* Chat Shortcut */}
                    {prompt.command && (
                        <div>
                            <h3 className="text-xs font-semibold text-muted-foreground mb-2">Chat Shortcut</h3>
                            <div>
                                <span className="inline-block font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 rounded">
                                    /{prompt.command}
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Start New Chat Button */}
                {onUseInChat && (
                    <div className="flex justify-center">
                        <Button
                            onClick={handleUseInChat}
                            className="w-full max-w-xl bg-[var(--color-brand-wMain)] hover:bg-[var(--color-brand-wMain)]/90 text-white"
                            size="lg"
                        >
                            <SquarePen className="h-4 w-4 mr-2" />
                            Start New Chat
                        </Button>
                    </div>
                )}

                {/* Content - no background */}
                {prompt.production_prompt && (
                    <div>
                        <h3 className="text-xs font-semibold text-muted-foreground mb-2">Content</h3>
                        <div className="text-xs font-mono whitespace-pre-wrap break-words">
                            {prompt.production_prompt.prompt_text.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                if (part.match(/\{\{[^}]+\}\}/)) {
                                    return (
                                        <span key={index} className="bg-primary/20 text-primary font-medium px-1 rounded">
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
            <div className="p-4 border-t bg-background space-y-2">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <User size={12} />
                    <span>Created by: {prompt.author_name || prompt.user_id}</span>
                </div>
                {prompt.updated_at && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Calendar size={12} />
                        <span>Last updated: {formatPromptDate(prompt.updated_at)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};