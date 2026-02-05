import React, { useState, useMemo, useEffect, useRef } from "react";
import { X, Filter, Sparkles, Plus } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";

import { PromptCard } from "./PromptCard";
import { CreatePromptCard } from "./CreatePromptCard";
import { PromptDetailSidePanel } from "./PromptDetailSidePanel";
import { EmptyState } from "../common";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { Button, SearchInput } from "@/lib/components/ui";
import { useConfigContext } from "@/lib/hooks";

interface PromptCardsProps {
    prompts: PromptGroup[];
    onManualCreate: () => void;
    onAIAssisted: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
    onExport?: (prompt: PromptGroup) => void;
    newlyCreatedPromptId?: string | null;
}

export const PromptCards: React.FC<PromptCardsProps> = ({ prompts, onManualCreate, onAIAssisted, onEdit, onDelete, onViewVersions, onUseInChat, onTogglePin, onExport, newlyCreatedPromptId }) => {
    const [selectedPrompt, setSelectedPrompt] = useState<PromptGroup | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
    const promptRefs = useRef<Map<string, HTMLDivElement>>(new Map());

    const { configFeatureEnablement } = useConfigContext();
    const aiAssistedEnabled = configFeatureEnablement?.promptAIAssisted ?? true;

    const handlePromptClick = (prompt: PromptGroup) => {
        setSelectedPrompt(prev => (prev?.id === prompt.id ? null : prompt));
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
            if (a.isPinned !== b.isPinned) {
                return a.isPinned ? -1 : 1;
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
            <ResizablePanelGroup id="promptCardsPanelGroup" direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedPrompt ? 70 : 100} minSize={50} maxSize={selectedPrompt ? 100 : 100} id="promptCardsMainPanel">
                    <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                        {!isLibraryEmpty && (
                            <div className="mb-4 flex items-center gap-2">
                                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="promptSearchInput" />

                                {/* Category Filter Dropdown */}
                                {categories.length > 0 && (
                                    <div className="relative">
                                        <Button onClick={() => setShowCategoryDropdown(!showCategoryDropdown)} variant="outline" testid="promptTags">
                                            <Filter size={16} />
                                            Tags
                                            {selectedCategories.length > 0 && <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">{selectedCategories.length}</span>}
                                        </Button>

                                        {showCategoryDropdown && (
                                            <>
                                                {/* Backdrop */}
                                                <div className="fixed inset-0 z-10" onClick={() => setShowCategoryDropdown(false)} />

                                                {/* Dropdown */}
                                                <div className="bg-background absolute top-full left-0 z-20 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border shadow-lg">
                                                    {selectedCategories.length > 0 && (
                                                        <div className="border-b">
                                                            <button
                                                                data-testid="clearFiltersButton"
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
                                                                <input data-testid={`category-checkbox-${category}`} type="checkbox" checked={selectedCategories.includes(category)} onChange={() => toggleCategory(category)} className="rounded" />
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
                                    <Button variant="ghost" onClick={clearAllFilters} data-testid="clearAllFiltersButton">
                                        <X size={16} />
                                        Clear All
                                    </Button>
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
                            <EmptyState title="No Prompts Found" subtitle="Create prompts to support reusable text structures for chat interactions." variant="noImage" buttons={createButtons} />
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <div className="flex flex-wrap gap-6">
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
                                            <PromptCard
                                                prompt={prompt}
                                                isSelected={selectedPrompt?.id === prompt.id}
                                                onPromptClick={() => handlePromptClick(prompt)}
                                                onEdit={onEdit}
                                                onDelete={onDelete}
                                                onViewVersions={onViewVersions}
                                                onUseInChat={onUseInChat}
                                                onTogglePin={onTogglePin}
                                                onExport={onExport}
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
                        <ResizablePanel defaultSize={30} minSize={20} maxSize={50} id="promptDetailSidePanel">
                            <PromptDetailSidePanel prompt={selectedPrompt} onClose={handleCloseSidePanel} onEdit={onEdit} onDelete={onDelete} onViewVersions={onViewVersions} onUseInChat={onUseInChat} onTogglePin={onTogglePin} onExport={onExport} />
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};
