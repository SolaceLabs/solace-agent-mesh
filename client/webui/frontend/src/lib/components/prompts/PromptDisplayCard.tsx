import React from "react";
import type { ReactNode } from "react";

import { Command, Pencil, Trash2, FileText, Tag, Calendar, History } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";
import { formatPromptDate } from "@/lib/utils/promptUtils";
import { useConfigContext } from "@/lib/hooks";

interface DetailItemProps {
    label: string;
    value?: string | null | ReactNode;
    icon?: ReactNode;
    fullWidthValue?: boolean;
}

interface PromptDisplayCardProps {
    prompt: PromptGroup;
    isExpanded: boolean;
    onToggleExpand: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
}

const DetailItem: React.FC<DetailItemProps> = ({ label, value, icon, fullWidthValue = false }) => {
    if (value === undefined || value === null || (typeof value === "string" && !value.trim())) return null;
    return (
        <div className={`mb-1.5 flex text-sm ${fullWidthValue ? "flex-col items-start" : "items-center"}`}>
            <div className="flex w-36 flex-shrink-0 items-center text-sm font-semibold text-nowrap">
                {icon && <span className="mr-2">{icon}</span>}
                {label}:
            </div>
            <div className={`text-accent-foreground text-sm ${fullWidthValue ? "mt-1 w-full" : "truncate"}`} title={typeof value === "string" ? value : undefined}>
                {value}
            </div>
        </div>
    );
};

export const PromptDisplayCard: React.FC<PromptDisplayCardProps> = ({ prompt, isExpanded, onToggleExpand, onEdit, onDelete, onViewVersions }) => {
    const { configFeatureEnablement } = useConfigContext();
    const versionHistoryEnabled = configFeatureEnablement?.promptVersionHistory ?? true;
    
    // Only show version history if enabled and callback provided
    const showVersionHistory = versionHistoryEnabled && onViewVersions;
    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        onEdit(prompt);
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        onDelete(prompt.id, prompt.name);
    };

    const handleViewVersions = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onViewVersions) {
            onViewVersions(prompt);
        }
    };

    const handleViewVersionsFront = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (onViewVersions) {
            onViewVersions(prompt);
        }
    };

    return (
        <div className="bg-card h-[400px] w-full flex-shrink-0 cursor-pointer rounded-lg sm:w-[380px]" onClick={onToggleExpand} role="button" tabIndex={0} aria-expanded={isExpanded}>
            {/* Front face */}
            <div className={`transform-style-preserve-3d relative h-full w-full transition-transform duration-700 ${isExpanded ? "rotate-y-180" : ""}`} style={{ transformStyle: "preserve-3d" }}>
                <div className="absolute flex h-full w-full flex-col overflow-hidden rounded-lg border shadow-xl" style={{ backfaceVisibility: "hidden", transform: "rotateY(0deg)" }}>
                    <div className="flex items-center justify-between p-4">
                        <div className="flex min-w-0 items-center flex-1">
                            <Command className="mr-3 h-8 w-8 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                            <div className="min-w-0">
                                <h2 className="truncate text-xl font-semibold" title={prompt.name}>
                                    {prompt.name}
                                </h2>
                                {prompt.command && (
                                    <span className="inline-block font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 rounded mt-1">
                                        /{prompt.command}
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="flex gap-1 ml-2">
                            <button
                                onClick={handleEdit}
                                className="p-1.5 rounded hover:bg-muted transition-colors"
                                title="Edit"
                            >
                                <Pencil size={16} />
                            </button>
                            {showVersionHistory && (
                                <button
                                    onClick={handleViewVersionsFront}
                                    className="p-1.5 rounded hover:bg-muted transition-colors"
                                    title="Version History"
                                >
                                    <History size={16} />
                                </button>
                            )}
                            <button
                                onClick={handleDelete}
                                className="p-1.5 rounded hover:bg-muted transition-colors"
                                title="Delete"
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>
                    </div>
                    <div className="flex flex-col flex-grow overflow-hidden p-4">
                        {prompt.category && (
                            <div className="mb-3">
                                <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-0.5 rounded-full bg-primary/10 text-primary">
                                    <Tag size={12} />
                                    {prompt.category}
                                </span>
                            </div>
                        )}
                        <div className="mb-4 text-base leading-6 line-clamp-3">{prompt.description || "No description provided."}</div>
                        {prompt.production_prompt && (
                            <div className="flex flex-col flex-shrink-0">
                                <div className="text-sm font-semibold mb-2 flex items-center">
                                    <FileText size={14} className="mr-2" />
                                    Preview:
                                </div>
                                <div className="relative text-xs text-muted-foreground font-mono bg-muted/50 p-2 rounded h-[6rem] overflow-hidden">
                                    <p className="whitespace-pre-wrap break-words">
                                        {prompt.production_prompt.prompt_text}
                                    </p>
                                    <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-muted/50 to-transparent pointer-events-none flex items-end justify-end pb-1 pr-2">
                                        <span className="text-[10px] text-primary/80 font-sans font-medium">View more</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                    <div data-testid="clickForDetails" className="text-accent-foreground border-t p-2 text-center text-sm">
                        Click for details
                    </div>
                </div>

                {/* Back face */}
                <div className="absolute flex h-full w-full flex-col overflow-hidden rounded-lg border shadow-xl" style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
                    <div className="flex items-center justify-between p-3">
                        <h3 className="text-md truncate font-semibold" title={prompt.name}>
                            Details: {prompt.name}
                        </h3>
                    </div>
                    <div className="scrollbar-themed flex-grow space-y-1.5 overflow-y-auto p-3 text-xs">
                        <DetailItem label="Name" value={prompt.name} icon={<Command size={14} />} />
                        {prompt.command && (
                            <DetailItem label="Command" value={`/${prompt.command}`} icon={<Command size={14} />} />
                        )}
                        <DetailItem label="Description" value={prompt.description} icon={<FileText size={14} />} fullWidthValue />
                        {prompt.category && (
                            <DetailItem label="Category" value={prompt.category} icon={<Tag size={14} />} />
                        )}
                        <DetailItem label="Created" value={formatPromptDate(prompt.created_at)} icon={<Calendar size={14} />} />
                        {prompt.updated_at && (
                            <DetailItem label="Updated" value={formatPromptDate(prompt.updated_at)} icon={<Calendar size={14} />} />
                        )}
                        
                        {prompt.production_prompt && (
                            <div className="mt-3 border-t pt-3">
                                <h4 className="mb-2 text-xs font-semibold flex items-center">
                                    <FileText size={14} className="mr-2" />
                                    Production Prompt
                                </h4>
                                <div className="bg-muted/50 p-2 rounded">
                                    <p className="text-xs font-mono whitespace-pre-wrap break-words">
                                        {prompt.production_prompt.prompt_text}
                                    </p>
                                </div>
                            </div>
                        )}

                        <div className="mt-3 border-t pt-3 space-y-2">
                            <div className="flex gap-2">
                                <button
                                    onClick={handleEdit}
                                    className="flex-1 flex items-center justify-center gap-2 rounded bg-primary/10 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
                                >
                                    <Pencil size={14} />
                                    Edit
                                </button>
                                <button
                                    onClick={handleDelete}
                                    className="flex-1 flex items-center justify-center gap-2 rounded bg-muted px-3 py-2 text-xs font-medium hover:bg-muted/80 transition-colors"
                                >
                                    <Trash2 size={14} />
                                    Delete
                                </button>
                            </div>
                            {showVersionHistory && (
                                <button
                                    onClick={handleViewVersions}
                                    className="w-full flex items-center justify-center gap-2 rounded bg-muted px-3 py-2 text-xs font-medium hover:bg-muted/80 transition-colors"
                                >
                                    <History size={14} />
                                    View Version History
                                </button>
                            )}
                        </div>
                    </div>
                    <div className="text-accent-foreground border-t p-2 text-center text-sm">Click for summary</div>
                </div>
            </div>
        </div>
    );
};