import React, { useState, useMemo } from "react";
import { X, Filter } from "lucide-react";

import type { SkillSummary, Skill } from "@/lib/types/skills";

import { SkillCard } from "./SkillCard";
import { SkillDetailSidePanel } from "./SkillDetailSidePanel";
import { EmptyState } from "../common";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui/resizable";
import { Button, SearchInput } from "@/lib/components/ui";
import { authenticatedFetch } from "@/lib/utils";

interface SkillCardsProps {
    skills: SkillSummary[];
    onUseInChat?: (skill: Skill) => void;
    onExport?: (skill: Skill) => void;
}

export const SkillCards: React.FC<SkillCardsProps> = ({ skills, onUseInChat, onExport }) => {
    const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
    const [selectedSkillDetail, setSelectedSkillDetail] = useState<Skill | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
    const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
    const [showScopeDropdown, setShowScopeDropdown] = useState(false);
    const [showTypeDropdown, setShowTypeDropdown] = useState(false);
    const [isLoadingDetail, setIsLoadingDetail] = useState(false);

    // Map API response (snake_case) to frontend type (camelCase)
    const mapApiResponseToSkill = (apiResponse: Record<string, unknown>): Skill => {
        return {
            id: apiResponse.id as string,
            name: apiResponse.name as string,
            description: apiResponse.description as string,
            type: apiResponse.type as Skill["type"],
            scope: apiResponse.scope as Skill["scope"],
            ownerUserId: apiResponse.owner_user_id as string | undefined,
            ownerAgent: apiResponse.owner_agent as string | undefined,
            tags: (apiResponse.tags as string[]) || [],
            steps: ((apiResponse.steps as Record<string, unknown>[]) || []).map(step => ({
                stepNumber: step.step_number as number,
                description: step.description as string,
                toolName: step.tool_name as string | undefined,
                toolParameters: step.tool_parameters as Record<string, unknown> | undefined,
                expectedOutput: step.expected_output as string | undefined,
                agentName: step.agent_name as string | undefined,
            })),
            agentChain: ((apiResponse.agent_chain as Record<string, unknown>[]) || []).map(node => ({
                agentName: node.agent_name as string,
                order: node.order as number,
                role: node.role as string | undefined,
                toolsUsed: (node.tools_used as string[]) || [],
            })),
            preconditions: (apiResponse.preconditions as string[]) || [],
            postconditions: (apiResponse.postconditions as string[]) || [],
            successCount: (apiResponse.success_count as number) || 0,
            failureCount: (apiResponse.failure_count as number) || 0,
            usageCount: (apiResponse.usage_count as number) || 0,
            successRate: apiResponse.success_rate as number | undefined,
            isActive: (apiResponse.is_active as boolean) ?? true,
            createdAt: (apiResponse.created_at as string) || "",
            updatedAt: (apiResponse.updated_at as string) || "",
            metadata: apiResponse.metadata as Record<string, unknown> | undefined,
            summary: apiResponse.summary as string | undefined,
            markdownContent: apiResponse.markdown_content as string | undefined,
            involvedAgents: apiResponse.involved_agents as string[] | undefined,
        };
    };

    const handleSkillClick = async (skill: SkillSummary) => {
        if (selectedSkillId === skill.id) {
            // Deselect
            setSelectedSkillId(null);
            setSelectedSkillDetail(null);
        } else {
            // Select and fetch full details
            setSelectedSkillId(skill.id);
            setIsLoadingDetail(true);
            try {
                const response = await authenticatedFetch(`/api/v1/skills/${skill.id}`);
                if (response.ok) {
                    const apiResponse = await response.json();
                    const detail = mapApiResponseToSkill(apiResponse);
                    setSelectedSkillDetail(detail);
                } else {
                    // If fetch fails, use summary data as fallback
                    setSelectedSkillDetail({
                        ...skill,
                        steps: [],
                        agentChain: [],
                        preconditions: [],
                        postconditions: [],
                        successCount: 0,
                        failureCount: 0,
                        createdAt: "",
                        updatedAt: "",
                    } as Skill);
                }
            } catch (error) {
                console.error("Failed to fetch skill details:", error);
                // Use summary data as fallback
                setSelectedSkillDetail({
                    ...skill,
                    steps: [],
                    agentChain: [],
                    preconditions: [],
                    postconditions: [],
                    successCount: 0,
                    failureCount: 0,
                    createdAt: "",
                    updatedAt: "",
                } as Skill);
            } finally {
                setIsLoadingDetail(false);
            }
        }
    };

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
            const matchesSearch = skill.name?.toLowerCase().includes(searchQuery.toLowerCase()) || skill.description?.toLowerCase().includes(searchQuery.toLowerCase()) || skill.ownerAgent?.toLowerCase().includes(searchQuery.toLowerCase());

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

    return (
        <div className="absolute inset-0 h-full w-full">
            <ResizablePanelGroup id="skillCardsPanelGroup" direction="horizontal" className="h-full">
                <ResizablePanel defaultSize={selectedSkillId ? 70 : 100} minSize={50} maxSize={selectedSkillId ? 100 : 100} id="skillCardsMainPanel">
                    <div className="flex h-full flex-col pt-6 pb-6 pl-6">
                        {!isLibraryEmpty && (
                            <div className="mb-4 flex items-center gap-2">
                                <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="skillSearchInput" />

                                {/* Scope Filter Dropdown */}
                                {scopes.length > 0 && (
                                    <div className="relative">
                                        <Button onClick={() => setShowScopeDropdown(!showScopeDropdown)} variant="outline" testid="skillScopes">
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
                                        <Button onClick={() => setShowTypeDropdown(!showTypeDropdown)} variant="outline" testid="skillTypes">
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
                                    {/* Skill Cards */}
                                    {filteredSkills.map(skill => (
                                        <SkillCard
                                            key={skill.id}
                                            skill={skill}
                                            isSelected={selectedSkillId === skill.id}
                                            onSkillClick={() => handleSkillClick(skill)}
                                            onUseInChat={
                                                onUseInChat
                                                    ? s => {
                                                          // Convert SkillSummary to Skill for the handler
                                                          const fullSkill: Skill = {
                                                              ...s,
                                                              steps: [],
                                                              agentChain: [],
                                                              preconditions: [],
                                                              postconditions: [],
                                                              successCount: 0,
                                                              failureCount: 0,
                                                              createdAt: "",
                                                              updatedAt: "",
                                                          };
                                                          onUseInChat(fullSkill);
                                                      }
                                                    : undefined
                                            }
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
                        <ResizablePanel defaultSize={30} minSize={20} maxSize={50} id="skillDetailSidePanel">
                            {isLoadingDetail ? (
                                <div className="flex h-full items-center justify-center">
                                    <div className="text-muted-foreground">Loading...</div>
                                </div>
                            ) : (
                                <SkillDetailSidePanel skill={selectedSkillDetail} onClose={handleCloseSidePanel} onUseInChat={onUseInChat} onExport={onExport} />
                            )}
                        </ResizablePanel>
                    </>
                )}
            </ResizablePanelGroup>
        </div>
    );
};
