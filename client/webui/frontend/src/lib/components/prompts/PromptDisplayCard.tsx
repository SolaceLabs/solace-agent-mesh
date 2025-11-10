import React, { useState } from "react";

import { Pencil, Trash2, FileText, Tag, History, MoreHorizontal, MessageSquare, Star } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";
import { useConfigContext } from "@/lib/hooks";
import {
    Button,
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/lib/components/ui";

interface PromptDisplayCardProps {
    prompt: PromptGroup;
    isSelected: boolean;
    onPromptClick: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
}

export const PromptDisplayCard: React.FC<PromptDisplayCardProps> = ({ prompt, isSelected, onPromptClick, onEdit, onDelete, onViewVersions, onUseInChat, onTogglePin }) => {
    const { configFeatureEnablement } = useConfigContext();
    const versionHistoryEnabled = configFeatureEnablement?.promptVersionHistory ?? true;
    const [dropdownOpen, setDropdownOpen] = useState(false);
    
    // Only show version history if enabled and callback provided
    const showVersionHistory = versionHistoryEnabled && onViewVersions;
    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onEdit(prompt);
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        onDelete(prompt.id, prompt.name);
    };

    const handleViewVersions = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        if (onViewVersions) {
            onViewVersions(prompt);
        }
    };

    const handleUseInChat = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        if (onUseInChat) {
            onUseInChat(prompt);
        }
    };

    const handleTogglePin = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onTogglePin) {
            onTogglePin(prompt.id, prompt.is_pinned);
        }
    };

    return (
        <div
            className={`bg-card h-[200px] w-full flex-shrink-0 cursor-pointer rounded-lg sm:w-[380px] transition-all ${
                isSelected ? 'ring-2 ring-primary ring-inset' : ''
            }`}
            onClick={onPromptClick}
            role="button"
            tabIndex={0}
        >
            <div className="flex h-full w-full flex-col overflow-hidden rounded-lg border shadow-xl">
                    <div className="flex items-center justify-between p-4">
                        <div className="flex min-w-0 items-center gap-2 flex-1">
                            <FileText className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                            <div className="min-w-0">
                                <h2 className="truncate text-lg font-semibold" title={prompt.name}>
                                    {prompt.name}
                                </h2>
                            </div>
                        </div>
                        <div className="flex items-center gap-1">
                            {onTogglePin && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={handleTogglePin}
                                    className={prompt.is_pinned ? 'text-primary' : 'text-muted-foreground'}
                                    tooltip={prompt.is_pinned ? "Remove from favorites" : "Add to favorites"}
                                >
                                    <Star size={16} fill={prompt.is_pinned ? 'currentColor' : 'none'} />
                                </Button>
                            )}
                            <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setDropdownOpen(!dropdownOpen);
                                    }}
                                    tooltip="Actions"
                                    className="cursor-pointer"
                                >
                                    <MoreHorizontal size={16} />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                                {onUseInChat && (
                                    <DropdownMenuItem onClick={handleUseInChat}>
                                        <MessageSquare size={14} className="mr-2" />
                                        Use in Chat
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
                        </div>
                    </div>
                    <div className="flex flex-col flex-grow overflow-hidden px-4 pb-4 pt-0">
                        <div className="text-xs text-muted-foreground mb-2">
                            By {prompt.author_name || prompt.user_id}
                        </div>
                        <div className="mb-3 text-sm leading-5 line-clamp-2">{prompt.description || "No description provided."}</div>
                        <div className="mt-auto">
                            <div className="flex items-center gap-2 flex-wrap">
                                {prompt.command && (
                                    <span className="inline-block font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 rounded">
                                        /{prompt.command}
                                    </span>
                                )}
                                {prompt.category && (
                                    <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-primary/10 text-primary">
                                        <Tag size={12} />
                                        {prompt.category}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
            </div>
        </div>
    );
};