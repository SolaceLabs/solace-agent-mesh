import React, { useState } from "react";

import { Pencil, Trash2, NotepadText, Tag, History, MoreHorizontal, MessageSquare, Star, Download } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import type { PromptGroup } from "@/lib/types/prompts";
import { useConfigContext } from "@/lib/hooks";

interface PromptDisplayCardProps {
    prompt: PromptGroup;
    isSelected: boolean;
    onPromptClick: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
    onExport?: (prompt: PromptGroup) => void;
}

export const PromptCard: React.FC<PromptDisplayCardProps> = ({ prompt, isSelected, onPromptClick, onEdit, onDelete, onViewVersions, onUseInChat, onTogglePin, onExport }) => {
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
            onTogglePin(prompt.id, prompt.isPinned);
        }
    };

    const handleExport = (e: React.MouseEvent) => {
        e.stopPropagation();
        setDropdownOpen(false);
        if (onExport) {
            onExport(prompt);
        }
    };

    return (
        <GridCard data-testid={prompt.id} isSelected={isSelected} onClick={onPromptClick}>
            <div className="flex h-full w-full flex-col">
                <div className="flex items-center justify-between px-4">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                        <NotepadText className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                        <div className="min-w-0">
                            <h2 className="truncate text-lg font-semibold" title={prompt.name}>
                                {prompt.name}
                            </h2>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        {onTogglePin && (
                            <Button variant="ghost" size="icon" onClick={handleTogglePin} className={prompt.isPinned ? "text-primary" : "text-muted-foreground"} tooltip={prompt.isPinned ? "Remove from favorites" : "Add to favorites"}>
                                <Star size={16} fill={prompt.isPinned ? "currentColor" : "none"} />
                            </Button>
                        )}
                        <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={e => {
                                        e.stopPropagation();
                                        setDropdownOpen(!dropdownOpen);
                                    }}
                                    tooltip="Actions"
                                    className="cursor-pointer"
                                >
                                    <MoreHorizontal size={16} />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" onClick={e => e.stopPropagation()}>
                                {onUseInChat && (
                                    <DropdownMenuItem onClick={handleUseInChat}>
                                        <MessageSquare size={14} className="mr-2" />
                                        Use in New Chat
                                    </DropdownMenuItem>
                                )}
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
                    </div>
                </div>
                <div className="flex flex-grow flex-col overflow-hidden px-4">
                    <div className="text-muted-foreground mb-2 text-xs">By {prompt.authorName || prompt.userId}</div>
                    <div className="mb-3 line-clamp-2 text-sm leading-5">{prompt.description || "No description provided."}</div>
                    <div className="mt-auto">
                        <div className="flex flex-wrap items-center gap-2">
                            {prompt.command && <span className="text-primary bg-primary/10 inline-block rounded px-2 py-0.5 font-mono text-xs">/{prompt.command}</span>}
                            {prompt.category && (
                                <span className="bg-primary/10 text-primary inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium">
                                    <Tag size={12} />
                                    {prompt.category}
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </GridCard>
    );
};
