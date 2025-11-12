import React, { useState, useMemo, useEffect, useRef } from "react";
import { X, Filter, Sparkles, Plus } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";

import { PromptDisplayCard } from "./PromptDisplayCard";
import { CreatePromptCard } from "./CreatePromptCard";
import { PromptDetailSidePanel } from "./PromptDetailSidePanel";
import { EmptyState } from "../common";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { SearchInput } from "@/lib/components/ui";
import { useConfigContext } from "@/lib/hooks";

interface PromptMeshCardsProps {
    prompts: PromptGroup[];
    onManualCreate: () => void;
    onAIAssisted: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
    newlyCreatedPromptId?: string | null;
}

export const PromptMeshCards: React.FC<PromptMeshCardsProps> = ({ prompts, onManualCreate, onAIAssisted, onEdit, onDelete, onViewVersions, onUseInChat, onTogglePin, newlyCreatedPromptId }) => {
    const [selectedPrompt, setSelectedPrompt] = useState<PromptGroup | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
    const promptRefs = useRef<Map<string, HTMLDivElement>>(new Map());

    const { configFeatureEnablement } = useConfigContext();
    const aiAssistedEnabled = configFeatureEnablement?.promptAIAssisted ?? true;

    const handlePromptClick = (prompt: PromptGroup) => {
        setSelectedPrompt(prompt);
    };

    const handleCloseSidePanel = () => {
        setSelectedPrompt(null);
    };

    // Extract unique categories
    const categories = useMemo(() => {
        const cats = new Set<string>();
        prompts.forEach(prompt => {
            if (prompt.category) {
                cats.add(prompt.category);
            }
        });
        return Array.from(cats).sort();
    }, [prompts]);

    const filteredPrompts = useMemo(() => {
        const filtered = prompts.filter(prompt => {
            const matchesSearch = prompt.name?.toLowerCase().includes(searchQuery.toLowerCase()) || prompt.description?.toLowerCase().includes(searchQuery.toLowerCase()) || prompt.command?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesCategory = selectedCategories.length === 0 || (prompt.category && selectedCategories.includes(prompt.category));

            return matchesSearch && matchesCategory;
        });

        return filtered.sort((a, b) => {
            if (a.is_pinned !== b.is_pinned) {
                return a.is_pinned ? -1 : 1;
            }
            // Within each group, sort alphabetically by name
            const nameA = (a.name || "").toLowerCase();
            const nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB);
        });
    }, [prompts, searchQuery, selectedCategories]);

    const toggleCategory = (category: string) => {
        setSelectedCategories(prev => (prev.includes(category) ? prev.filter(c => c !== category) : [...prev, category]));
    };

    const clearCategories = () => {
        setSelectedCategories([]);
    };

    const clearAllFilters = () => {
        setSearchQuery("");
        setSelectedCategories([]);
    };

    const hasActiveFilters = searchQuery.length > 0 || selectedCategories.length > 0;

    const isLibraryEmpty = prompts.length === 0;

    // Auto-select and scroll to newly created prompt
    useEffect(() => {
        if (newlyCreatedPromptId && prompts.length > 0) {
            const newPrompt = prompts.find(p => p.id === newlyCreatedPromptId);
            if (newPrompt) {
                // Select the prompt
                setSelectedPrompt(newPrompt);

                // Scroll to it after a short delay to ensure rendering is complete
                setTimeout(() => {
                    const element = promptRefs.current.get(newlyCreatedPromptId);
                    if (element) {
                        element.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                }, 100);
            }
        }
    }, [newlyCreatedPromptId, prompts]);

    const createButtons = useMemo(() => {
        const buttons = [];
        if (aiAssistedEnabled) {
            buttons.push({
                icon: <Sparkles />,
                text: "Build with AI",
                variant: "default" as const,
                onClick: onAIAssisted,
            });
        }

        buttons.push({
            icon: <Plus />,
            text: "Create Manually",
            variant: "outline" as const,
            onClick: onManualCreate,
        });

        return buttons;
    }, [aiAssistedEnabled, onAIAssisted, onManualCreate]);

    return (
        <div className="absolute inset-0 h-full w-full">
            <ResizablePanelGroup direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedPrompt ? 70 : 100} minSize={50} maxSize={selectedPrompt ? 100 : 100}>
                    <div className="h-full overflow-hidden pt-6 pl-6">
                        {!isLibraryEmpty && (
                            <div className="mb-4 flex items-center gap-2">
                                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testId="promptSearchInput" />

                                {/* Category Filter Dropdown */}
                                {categories.length > 0 && (
                                    <div className="relative">
                                        <button onClick={() => setShowCategoryDropdown(!showCategoryDropdown)} className="bg-background hover:bg-muted flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors">
                                            <Filter size={16} />
                                            Tags
                                            {selectedCategories.length > 0 && <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">{selectedCategories.length}</span>}
                                        </button>

                                        {showCategoryDropdown && (
                                            <>
                                                {/* Backdrop */}
                                                <div className="fixed inset-0 z-10" onClick={() => setShowCategoryDropdown(false)} />

                                                {/* Dropdown */}
                                                <div className="bg-background absolute top-full left-0 z-20 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border shadow-lg">
                                                    {selectedCategories.length > 0 && (
                                                        <div className="border-b">
                                                            <button
                                                                onClick={clearCategories}
                                                                className="text-muted-foreground hover:text-foreground hover:bg-muted flex min-h-[24px] w-full cursor-pointer items-center gap-1 px-3 py-2 text-left text-xs transition-colors"
                                                            >
                                                                <X size={14} />
                                                                {selectedCategories.length === 1 ? "Clear Filter" : "Clear Filters"}
                                                            </button>
                                                        </div>
                                                    )}
                                                    <div className="p-1">
                                                        {categories.map(category => (
                                                            <label key={category} className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded px-2 py-1.5">
                                                                <input type="checkbox" checked={selectedCategories.includes(category)} onChange={() => toggleCategory(category)} className="rounded" />
                                                                <span className="text-sm">{category}</span>
                                                            </label>
                                                        ))}
                                                    </div>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                )}

                                {hasActiveFilters && (
                                    <button onClick={clearAllFilters} className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-sm whitespace-nowrap transition-colors" data-testid="clearAllFiltersButton">
                                        <X size={16} />
                                        Clear All
                                    </button>
                                )}
                            </div>
                        )}

                        {filteredPrompts.length === 0 && searchQuery ? (
                            <EmptyState
                                title="No Prompts Match Your Filter"
                                subtitle="Try adjusting your filter terms."
                                variant="notFound"
                                buttons={[
                                    {
                                        text: "Clear Filter",
                                        variant: "default",
                                        onClick: () => setSearchQuery(""),
                                    },
                                ]}
                            />
                        ) : isLibraryEmpty ? (
                            <EmptyState title="No Prompts Found" subtitle="Create prompts to facilitate repeated chat interactions." variant="noImage" buttons={createButtons} />
                        ) : (
                            <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                                <div className="flex flex-wrap gap-10">
                                    {/* Create New Prompt Card - Always first */}
                                    <CreatePromptCard onManualCreate={onManualCreate} onAIAssisted={onAIAssisted} />

                                    {/* Existing Prompt Cards */}
                                    {filteredPrompts.map(prompt => (
                                        <div
                                            key={prompt.id}
                                            ref={el => {
                                                if (el) {
                                                    promptRefs.current.set(prompt.id, el);
                                                } else {
                                                    promptRefs.current.delete(prompt.id);
                                                }
                                            }}
                                        >
                                            <PromptDisplayCard
                                                prompt={prompt}
                                                isSelected={selectedPrompt?.id === prompt.id}
                                                onPromptClick={() => handlePromptClick(prompt)}
                                                onEdit={onEdit}
                                                onDelete={onDelete}
                                                onViewVersions={onViewVersions}
                                                onUseInChat={onUseInChat}
                                                onTogglePin={onTogglePin}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </ResizablePanel>

                {/* Side Panel - resizable */}
                {selectedPrompt && (
                    <>
                        <ResizableHandle />
                        <ResizablePanel defaultSize={30} minSize={20} maxSize={50}>
                            <PromptDetailSidePanel prompt={selectedPrompt} onClose={handleCloseSidePanel} onEdit={onEdit} onDelete={onDelete} onViewVersions={onViewVersions} onUseInChat={onUseInChat} onTogglePin={onTogglePin} />
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};
