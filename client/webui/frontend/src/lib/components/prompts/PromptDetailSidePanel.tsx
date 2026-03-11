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
        <div className="flex h-full w-full flex-col border-l bg-(--background-w10)">
            {/* Header */}
            <div className="border-b p-4">
                <div className="mb-2 flex items-center justify-between">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <NotepadText className="h-6 w-6 flex-shrink-0 text-(--brand-wMain)" />
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
                {(prompt.productionPrompt?.category || prompt.category) && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-(--primary-w10) px-2.5 py-0.5 text-xs font-medium text-(--primary-wMain)">
                        <Tag size={12} />
                        {prompt.productionPrompt?.category || prompt.category}
                    </span>
                )}
            </div>

            {/* Content */}
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
                {/* Description and Chat Shortcut - with background */}
                <div className="space-y-6 rounded bg-(--secondary-w10) p-4">
                    {/* Description */}
                    <div>
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Description</h3>
                        <div className="text-sm leading-relaxed">{prompt.productionPrompt?.description || prompt.description || "No description provided."}</div>
                    </div>

                    {/* Chat Shortcut */}
                    {(prompt.productionPrompt?.command || prompt.command) && (
                        <div>
                            <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Chat Shortcut</h3>
                            <div>
                                <span className="inline-block rounded bg-(--primary-w10) px-2 py-0.5 font-mono text-xs text-(--info-wMain)">/{prompt.productionPrompt?.command || prompt.command}</span>
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
                        <h3 className="mb-2 text-xs font-semibold text-(--secondary-text-wMain)">Content</h3>
                        <div className="font-mono text-xs break-words whitespace-pre-wrap">
                            {prompt.productionPrompt.promptText.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                if (part.match(/\{\{[^}]+\}\}/)) {
                                    return (
                                        <span key={index} className="rounded bg-(--primary-w20) px-1 font-medium text-(--primary-wMain)">
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
            <div className="space-y-2 border-t bg-(--background-w10) p-4">
                <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                    <User size={12} />
                    <span>Created by: {prompt.authorName || prompt.userId}</span>
                </div>
                {prompt.updatedAt && (
                    <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                        <Calendar size={12} />
                        <span>Last updated: {formatPromptDate(prompt.updatedAt)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};
