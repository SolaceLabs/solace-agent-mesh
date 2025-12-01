import React, { useState, useMemo, useCallback } from "react";
import { X, Filter } from "lucide-react";

import type { SkillGroup, SkillGroupSummary } from "@/lib/types/versioned-skills";

import { SkillGroupCard } from "./SkillGroupCard";
import { SkillGroupDetailSidePanel } from "./SkillGroupDetailSidePanel";
import { EmptyState } from "../common";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { Button, SearchInput } from "@/lib/components/ui";
import * as versionedSkillsApi from "@/lib/services/versionedSkillsApi";

interface SkillGroupCardsProps {
    skills: SkillGroupSummary[];
    onUseInChat?: (skill: SkillGroup) => void;
    onExport?: (skill: SkillGroup) => void;
    onViewVersions?: (skill: SkillGroup) => void;
    onDelete?: (id: string, name: string) => void;
}

export const SkillGroupCards: React.FC<SkillGroupCardsProps> = ({ skills, onUseInChat, onExport, onViewVersions, onDelete }) => {
    const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
    const [selectedSkillDetail, setSelectedSkillDetail] = useState<SkillGroup | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
    const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
    const [showScopeDropdown, setShowScopeDropdown] = useState(false);
    const [showTypeDropdown, setShowTypeDropdown] = useState(false);
    const [isLoadingDetail, setIsLoadingDetail] = useState(false);

    const handleSkillClick = useCallback(
        async (skill: SkillGroupSummary) => {
            if (selectedSkillId === skill.id) {
                // Deselect
                setSelectedSkillId(null);
                setSelectedSkillDetail(null);
            } else {
                // Select and fetch full details
                setSelectedSkillId(skill.id);
                setIsLoadingDetail(true);
                try {
                    const detail = await versionedSkillsApi.getSkillGroup(skill.id, true);
                    setSelectedSkillDetail(detail);
                } catch (error) {
                    console.error("Failed to fetch skill details:", error);
                    // Use summary data as fallback
                    setSelectedSkillDetail({
                        id: skill.id,
                        name: skill.name,
                        description: skill.description,
                        category: skill.category,
                        type: skill.type,
                        scope: skill.scope,
                        ownerAgentName: skill.ownerAgentName,
                        isArchived: skill.isArchived,
                        versionCount: skill.versionCount,
                        successRate: skill.successRate,
                        createdAt: "",
                        updatedAt: "",
                    } as SkillGroup);
                } finally {
                    setIsLoadingDetail(false);
                }
            }
        },
        [selectedSkillId]
    );

    const handleCloseSidePanel = () => {
        setSelectedSkillId(null);
        setSelectedSkillDetail(null);
    };

    // Extract unique scopes and types
    const scopes = useMemo(() => {
        const scopeSet = new Set<string>();
        skills.forEach(skill => {
            if (skill.scope) {
                scopeSet.add(skill.scope);
            }
        });
        return Array.from(scopeSet).sort();
    }, [skills]);

    const types = useMemo(() => {
        const typeSet = new Set<string>();
        skills.forEach(skill => {
            if (skill.type) {
                typeSet.add(skill.type);
            }
        });
        return Array.from(typeSet).sort();
    }, [skills]);

    const filteredSkills = useMemo(() => {
        return skills.filter(skill => {
            const matchesSearch =
                skill.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                skill.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                skill.ownerAgentName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                skill.category?.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesScope = selectedScopes.length === 0 || selectedScopes.includes(skill.scope);
            const matchesType = selectedTypes.length === 0 || selectedTypes.includes(skill.type);

            return matchesSearch && matchesScope && matchesType;
        });
    }, [skills, searchQuery, selectedScopes, selectedTypes]);

    const toggleScope = (scope: string) => {
        setSelectedScopes(prev => (prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]));
    };

    const toggleType = (type: string) => {
        setSelectedTypes(prev => (prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]));
    };

    const clearAllFilters = () => {
        setSearchQuery("");
        setSelectedScopes([]);
        setSelectedTypes([]);
    };

    const hasActiveFilters = searchQuery.length > 0 || selectedScopes.length > 0 || selectedTypes.length > 0;

    const isLibraryEmpty = skills.length === 0;

    // Handle use in chat with full skill data
    const handleUseInChat = useCallback(
        (skill: SkillGroupSummary) => {
            if (onUseInChat && selectedSkillDetail && selectedSkillDetail.id === skill.id) {
                onUseInChat(selectedSkillDetail);
            } else if (onUseInChat) {
                // Fetch full details first
                versionedSkillsApi
                    .getSkillGroup(skill.id, true)
                    .then(detail => {
                        onUseInChat(detail);
                    })
                    .catch(error => {
                        console.error("Failed to fetch skill for chat:", error);
                    });
            }
        },
        [onUseInChat, selectedSkillDetail]
    );

    // Handle view versions with full skill data
    const handleViewVersions = useCallback(
        (skill: SkillGroupSummary) => {
            if (onViewVersions && selectedSkillDetail && selectedSkillDetail.id === skill.id) {
                onViewVersions(selectedSkillDetail);
            } else if (onViewVersions) {
                // Fetch full details first
                versionedSkillsApi
                    .getSkillGroup(skill.id, true)
                    .then(detail => {
                        onViewVersions(detail);
                    })
                    .catch(error => {
                        console.error("Failed to fetch skill for version history:", error);
                    });
            }
        },
        [onViewVersions, selectedSkillDetail]
    );

    // Handle export with full skill data
    const handleExport = useCallback(
        (skill: SkillGroupSummary) => {
            if (onExport && selectedSkillDetail && selectedSkillDetail.id === skill.id) {
                onExport(selectedSkillDetail);
            } else if (onExport) {
                // Fetch full details first
                versionedSkillsApi
                    .getSkillGroup(skill.id, true)
                    .then(detail => {
                        onExport(detail);
                    })
                    .catch(error => {
                        console.error("Failed to fetch skill for export:", error);
                    });
            }
        },
        [onExport, selectedSkillDetail]
    );

    return (
        <div className="absolute inset-0 h-full w-full">
            <ResizablePanelGroup id="skillGroupCardsPanelGroup" direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedSkillId ? 70 : 100} minSize={50} maxSize={selectedSkillId ? 100 : 100} id="skillGroupCardsMainPanel">
                    <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                        {!isLibraryEmpty && (
                            <div className="mb-4 flex items-center gap-2">
                                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="skillGroupSearchInput" />

                                {/* Scope Filter Dropdown */}
                                {scopes.length > 0 && (
                                    <div className="relative">
                                        <Button onClick={() => setShowScopeDropdown(!showScopeDropdown)} variant="outline" testid="skillGroupScopes">
                                            <Filter size={16} />
                                            Scope
                                            {selectedScopes.length > 0 && <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">{selectedScopes.length}</span>}
                                        </Button>

                                        {showScopeDropdown && (
                                            <>
                                                {/* Backdrop */}
                                                <div className="fixed inset-0 z-10" onClick={() => setShowScopeDropdown(false)} />

                                                {/* Dropdown */}
                                                <div className="bg-background absolute top-full left-0 z-20 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border shadow-lg">
                                                    {selectedScopes.length > 0 && (
                                                        <div className="border-b">
                                                            <button
                                                                onClick={() => setSelectedScopes([])}
                                                                className="text-muted-foreground hover:text-foreground hover:bg-muted flex min-h-[24px] w-full cursor-pointer items-center gap-1 px-3 py-2 text-left text-xs transition-colors"
                                                            >
                                                                <X size={14} />
                                                                Clear Filters
                                                            </button>
                                                        </div>
                                                    )}
                                                    <div className="p-1">
                                                        {scopes.map(scope => (
                                                            <label key={scope} className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded px-2 py-1.5">
                                                                <input type="checkbox" checked={selectedScopes.includes(scope)} onChange={() => toggleScope(scope)} className="rounded" />
                                                                <span className="text-sm capitalize">{scope}</span>
                                                            </label>
                                                        ))}
                                                    </div>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                )}

                                {/* Type Filter Dropdown */}
                                {types.length > 0 && (
                                    <div className="relative">
                                        <Button onClick={() => setShowTypeDropdown(!showTypeDropdown)} variant="outline" testid="skillGroupTypes">
                                            <Filter size={16} />
                                            Type
                                            {selectedTypes.length > 0 && <span className="bg-primary text-primary-foreground rounded-full px-2 py-0.5 text-xs">{selectedTypes.length}</span>}
                                        </Button>

                                        {showTypeDropdown && (
                                            <>
                                                {/* Backdrop */}
                                                <div className="fixed inset-0 z-10" onClick={() => setShowTypeDropdown(false)} />

                                                {/* Dropdown */}
                                                <div className="bg-background absolute top-full left-0 z-20 mt-1 max-h-[300px] min-w-[200px] overflow-y-auto rounded-md border shadow-lg">
                                                    {selectedTypes.length > 0 && (
                                                        <div className="border-b">
                                                            <button
                                                                onClick={() => setSelectedTypes([])}
                                                                className="text-muted-foreground hover:text-foreground hover:bg-muted flex min-h-[24px] w-full cursor-pointer items-center gap-1 px-3 py-2 text-left text-xs transition-colors"
                                                            >
                                                                <X size={14} />
                                                                Clear Filters
                                                            </button>
                                                        </div>
                                                    )}
                                                    <div className="p-1">
                                                        {types.map(type => (
                                                            <label key={type} className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded px-2 py-1.5">
                                                                <input type="checkbox" checked={selectedTypes.includes(type)} onChange={() => toggleType(type)} className="rounded" />
                                                                <span className="text-sm capitalize">{type}</span>
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

                        {filteredSkills.length === 0 && searchQuery ? (
                            <EmptyState
                                title="No Skills Match Your Filter"
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
                            <EmptyState title="No Skills Found" subtitle="Skills are learned from successful task executions or authored manually. Start using the chat to build your skill library." variant="noImage" />
                        ) : (
                            <div className="flex-1 overflow-y-auto">
                                <div className="flex flex-wrap gap-6">
                                    {/* Skill Group Cards */}
                                    {filteredSkills.map(skill => (
                                        <SkillGroupCard
                                            key={skill.id}
                                            skill={skill}
                                            isSelected={selectedSkillId === skill.id}
                                            onSkillClick={() => handleSkillClick(skill)}
                                            onUseInChat={onUseInChat ? () => handleUseInChat(skill) : undefined}
                                            onViewVersions={onViewVersions ? () => handleViewVersions(skill) : undefined}
                                            onDelete={onDelete}
                                            onExport={onExport ? () => handleExport(skill) : undefined}
                                        />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </ResizablePanel>

                {/* Side Panel - resizable */}
                {selectedSkillId && (
                    <>
                        <ResizableHandle />
                        <ResizablePanel defaultSize={30} minSize={20} maxSize={50} id="skillGroupDetailSidePanel">
                            {isLoadingDetail ? (
                                <div className="flex h-full items-center justify-center">
                                    <div className="text-muted-foreground">Loading...</div>
                                </div>
                            ) : (
                                <SkillGroupDetailSidePanel skill={selectedSkillDetail} onClose={handleCloseSidePanel} onUseInChat={onUseInChat} onExport={onExport} onViewVersions={onViewVersions} onDelete={onDelete} />
                            )}
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};
