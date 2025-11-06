import React, { useState, useMemo } from "react";
import { X, Filter } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";

import { PromptDisplayCard } from "./PromptDisplayCard";
import { CreatePromptCard } from "./CreatePromptCard";
import { PromptDetailSidePanel } from "./PromptDetailSidePanel";
import { EmptyState } from "../common";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";

interface PromptMeshCardsProps {
    prompts: PromptGroup[];
    onManualCreate: () => void;
    onAIAssisted: () => void;
    onEdit: (prompt: PromptGroup) => void;
    onDelete: (id: string, name: string) => void;
    onViewVersions?: (prompt: PromptGroup) => void;
    onUseInChat?: (prompt: PromptGroup) => void;
    onTogglePin?: (id: string, currentStatus: boolean) => void;
}

export const PromptMeshCards: React.FC<PromptMeshCardsProps> = ({
    prompts,
    onManualCreate,
    onAIAssisted,
    onEdit,
    onDelete,
    onViewVersions,
    onUseInChat,
    onTogglePin
}) => {
    const [selectedPrompt, setSelectedPrompt] = useState<PromptGroup | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
    const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);

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
            const matchesSearch =
                prompt.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                prompt.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                prompt.command?.toLowerCase().includes(searchQuery.toLowerCase());
            
            const matchesCategory =
                selectedCategories.length === 0 ||
                (prompt.category && selectedCategories.includes(prompt.category));
            
            return matchesSearch && matchesCategory;
        });
        
        // Sort: pinned first, then by created_at
        return filtered.sort((a, b) => {
            if (a.is_pinned !== b.is_pinned) {
                return a.is_pinned ? -1 : 1;
            }
            return b.created_at - a.created_at;
        });
    }, [prompts, searchQuery, selectedCategories]);

    const toggleCategory = (category: string) => {
        setSelectedCategories(prev =>
            prev.includes(category)
                ? prev.filter(c => c !== category)
                : [...prev, category]
        );
    };

    const clearCategories = () => {
        setSelectedCategories([]);
    };

    // Check if library is empty (no prompts at all)
    const isLibraryEmpty = prompts.length === 0;

    return (
        <div className="h-full w-full absolute inset-0">
            <ResizablePanelGroup direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedPrompt ? 70 : 100} minSize={50} maxSize={selectedPrompt ? 100 : 100}>
                    <div className="h-full pt-12 pl-12 overflow-hidden">
            {/* Only show search/filter when we have prompts */}
            {!isLibraryEmpty && (
                <div className="mb-4 flex items-center gap-2">
                    <input
                        type="text"
                        data-testid="promptSearchInput"
                        placeholder="Search..."
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        className="bg-background rounded-md border px-3 py-2"
                    />
                    
                    {/* Category Filter Dropdown */}
                    {categories.length > 0 && (
                    <div className="relative">
                        <button
                            onClick={() => setShowCategoryDropdown(!showCategoryDropdown)}
                            className="bg-background rounded-md border px-3 py-2 text-sm hover:bg-muted transition-colors flex items-center gap-2"
                        >
                            <Filter size={16} />
                            Tags
                            {selectedCategories.length > 0 && (
                                <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">
                                    {selectedCategories.length}
                                </span>
                            )}
                        </button>
                        
                        {showCategoryDropdown && (
                            <>
                                {/* Backdrop */}
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setShowCategoryDropdown(false)}
                                />
                                
                                {/* Dropdown */}
                                <div className="absolute top-full left-0 mt-1 z-20 bg-background border rounded-md shadow-lg min-w-[200px] max-h-[300px] overflow-y-auto">
                                    {selectedCategories.length > 0 && (
                                        <div className="border-b p-2">
                                            <button
                                                onClick={clearCategories}
                                                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                                            >
                                                <X size={12} />
                                                Clear all
                                            </button>
                                        </div>
                                    )}
                                    <div className="p-1">
                                        {categories.map(category => (
                                            <label
                                                key={category}
                                                className="flex items-center gap-2 px-2 py-1.5 hover:bg-muted rounded cursor-pointer"
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={selectedCategories.includes(category)}
                                                    onChange={() => toggleCategory(category)}
                                                    className="rounded"
                                                />
                                                <span className="text-sm">{category}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                    )}
                </div>
            )}

            {filteredPrompts.length === 0 && searchQuery ? (
                <EmptyState 
                    title="No prompts match your search" 
                    variant="noImage" 
                    buttons={[{ 
                        text: "Clear Search", 
                        variant: "default", 
                        onClick: () => setSearchQuery("") 
                    }]} 
                />
            ) : isLibraryEmpty ? (
                /* Center the Create Prompt Card when library is empty */
                <div className="flex items-center justify-center h-[calc(100vh-200px)]">
                    <CreatePromptCard
                        onManualCreate={onManualCreate}
                        onAIAssisted={onAIAssisted}
                        isCentered={true}
                    />
                </div>
                ) : (
                    <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                        <div className="flex flex-wrap gap-10">
                            {/* Create New Prompt Card - Always first */}
                            <CreatePromptCard
                                onManualCreate={onManualCreate}
                                onAIAssisted={onAIAssisted}
                            />
                            
                            {/* Existing Prompt Cards */}
                            {filteredPrompts.map(prompt => (
                                <PromptDisplayCard
                                    key={prompt.id}
                                    prompt={prompt}
                                    isSelected={selectedPrompt?.id === prompt.id}
                                    onPromptClick={() => handlePromptClick(prompt)}
                                    onEdit={onEdit}
                                    onDelete={onDelete}
                                    onViewVersions={onViewVersions}
                                    onUseInChat={onUseInChat}
                                    onTogglePin={onTogglePin}
                                />
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
                            <PromptDetailSidePanel
                                prompt={selectedPrompt}
                                onClose={handleCloseSidePanel}
                                onEdit={onEdit}
                                onDelete={onDelete}
                                onViewVersions={onViewVersions}
                                onUseInChat={onUseInChat}
                                onTogglePin={onTogglePin}
                            />
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};