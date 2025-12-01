import React, { useState, useEffect, useCallback, useRef } from "react";
import { Pencil, Trash2, MoreHorizontal, Check, Archive } from "lucide-react";
import type { SkillGroup, SkillVersion } from "@/lib/types/versioned-skills";
import { Header } from "@/lib/components/header";
import { Button, Label } from "@/lib/components/ui";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import { MessageBanner } from "@/lib/components/common";
import { MarkdownHTMLConverter } from "@/lib/components/common/MarkdownHTMLConverter";
import * as versionedSkillsApi from "@/lib/services/versionedSkillsApi";

interface SkillVersionHistoryPageProps {
    group: SkillGroup;
    onBack: () => void;
    onBackToSkillDetail: () => void;
    onEdit: (group: SkillGroup) => void;
    onDeleteAll: (id: string, name: string) => void;
    onRestoreVersion: (versionId: string) => Promise<void>;
}

// Format date for display
const formatSkillDate = (dateStr: string) => {
    if (!dateStr) return "Unknown";
    try {
        return new Date(dateStr).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return dateStr;
    }
};

export const SkillVersionHistoryPage: React.FC<SkillVersionHistoryPageProps> = ({ group, onBack, onEdit, onDeleteAll, onRestoreVersion }) => {
    const { addNotification } = useChatContext();
    const [versions, setVersions] = useState<SkillVersion[]>([]);
    const [selectedVersion, setSelectedVersion] = useState<SkillVersion | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [currentGroup, setCurrentGroup] = useState<SkillGroup>(group);
    const [showDeleteActiveError, setShowDeleteActiveError] = useState(false);
    const hasInitializedRef = useRef(false);

    // Update currentGroup when group prop changes
    useEffect(() => {
        setCurrentGroup(group);
    }, [group]);

    const fetchVersions = useCallback(
        async (preserveSelection = false) => {
            setIsLoading(true);
            try {
                const data = await versionedSkillsApi.listVersions(group.id);
                setVersions(data);

                // Use a function update to access the current selectedVersion without adding it to dependencies
                setSelectedVersion(currentSelected => {
                    // If preserving selection, try to keep the same version selected
                    if (preserveSelection && currentSelected) {
                        const stillExists = data.find((v: SkillVersion) => v.id === currentSelected.id);
                        if (stillExists) {
                            return stillExists;
                        } else {
                            // If the selected version was deleted, fall back to production
                            return data.find((v: SkillVersion) => v.id === group.productionVersion?.id) || data[0];
                        }
                    } else if (data.length > 0 && !hasInitializedRef.current) {
                        // Only set default selection on initial load
                        hasInitializedRef.current = true;
                        return data.find((v: SkillVersion) => v.id === group.productionVersion?.id) || data[0];
                    }
                    return currentSelected;
                });
            } catch (error) {
                console.error("Failed to fetch versions:", error);
                addNotification("Failed to fetch versions", "error");
            } finally {
                setIsLoading(false);
            }
        },
        [group.id, group.productionVersion?.id, addNotification]
    );

    const fetchGroupData = useCallback(async () => {
        try {
            const data = await versionedSkillsApi.getSkillGroup(group.id);
            setCurrentGroup(data);
        } catch (error) {
            console.error("Failed to fetch group data:", error);
        }
    }, [group.id]);

    useEffect(() => {
        // Preserve selection when the component updates (e.g., after editing)
        fetchVersions(true);
    }, [fetchVersions]);

    const handleEditVersion = () => {
        // Pass the group with the selected version as the production version
        // This allows editing any version, not just the active one
        const groupWithSelectedVersion: SkillGroup = {
            ...currentGroup,
            productionVersion: selectedVersion || currentGroup.productionVersion,
        };
        onEdit(groupWithSelectedVersion);
    };

    const handleDeleteVersion = async () => {
        if (!selectedVersion) return;

        // Prevent deleting the active version
        if (selectedVersion.id === currentGroup.productionVersion?.id) {
            setShowDeleteActiveError(true);
            setTimeout(() => setShowDeleteActiveError(false), 5000);
            return;
        }

        try {
            // Note: Individual version deletion would need a separate API endpoint
            // For now, we'll show a message that this isn't supported
            addNotification("Individual version deletion is not yet supported. Use 'Delete All Versions' to remove the entire skill.", "info");
        } catch (error) {
            console.error("Failed to delete version:", error);
            addNotification("Failed to delete version", "error");
        }
    };

    const handleRestoreVersion = async () => {
        if (selectedVersion && selectedVersion.id !== currentGroup.productionVersion?.id) {
            await onRestoreVersion(selectedVersion.id);
            // Refresh group data to get updated production_version_id
            await fetchGroupData();
            // Refetch versions to update the UI, preserving the current selection
            await fetchVersions(true);
        }
    };

    const isActiveVersion = selectedVersion?.id === currentGroup.productionVersion?.id;

    // Get scope badge color
    const getScopeBadgeClass = (scope: string) => {
        switch (scope) {
            case "global":
                return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
            case "agent":
                return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
            case "user":
                return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
            case "shared":
                return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
            default:
                return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
        }
    };

    // Get type badge color
    const getTypeBadgeClass = (type: string) => {
        switch (type) {
            case "learned":
                return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
            case "authored":
                return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
            default:
                return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
        }
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <Header
                title={`Version History: ${currentGroup.name}`}
                breadcrumbs={[{ label: "Skills", onClick: onBack }, { label: "Version History" }]}
                buttons={[
                    <DropdownMenu key="actions-menu">
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => versionedSkillsApi.archiveSkillGroup(currentGroup.id)}>
                                <Archive size={14} className="mr-2" />
                                Archive Skill
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => onDeleteAll(currentGroup.id, currentGroup.name)}>
                                <Trash2 size={14} className="mr-2" />
                                Delete All Versions
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>,
                ]}
            />

            {/* Error Banner */}
            {showDeleteActiveError && <MessageBanner variant="error" message="Cannot delete the active version. Please make another version active first." />}

            {/* Content */}
            <div className="flex min-h-0 flex-1">
                {/* Left Sidebar - Version List */}
                <div className="w-[300px] overflow-y-auto border-r">
                    <div className="p-4">
                        <h3 className="text-muted-foreground mb-3 text-sm font-semibold">Versions</h3>
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="border-primary size-6 animate-spin rounded-full border-2 border-t-transparent" />
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {versions.map(version => {
                                    const isActive = version.id === currentGroup.productionVersion?.id;
                                    const isSelected = selectedVersion?.id === version.id;

                                    return (
                                        <button key={version.id} onClick={() => setSelectedVersion(version)} className={`w-full p-3 text-left transition-colors ${isSelected ? "bg-primary/5" : "hover:bg-muted/50"}`}>
                                            <div className="mb-1 flex items-center justify-between">
                                                <span className="text-sm font-medium">Version {version.version}</span>
                                                {isActive && <span className="rounded-full bg-[var(--color-success-w20)] px-2 py-0.5 text-xs text-[var(--color-success-wMain)]">Active</span>}
                                            </div>
                                            <span className="text-muted-foreground text-xs">{formatSkillDate(version.createdAt)}</span>
                                            {version.creationReason && <div className="text-muted-foreground mt-1 truncate text-xs italic">{version.creationReason}</div>}
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Panel - Version Details */}
                <div className="flex-1 overflow-y-auto">
                    {selectedVersion ? (
                        <div className="p-6">
                            <div className="mx-auto max-w-4xl space-y-6">
                                {/* Header with actions */}
                                <div className="flex items-center justify-between">
                                    <h2 className="text-lg font-semibold">Version {selectedVersion.version} Details</h2>
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" size="sm">
                                                <MoreHorizontal className="h-4 w-4" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem onClick={handleEditVersion}>
                                                <Pencil size={14} className="mr-2" />
                                                Edit Version
                                            </DropdownMenuItem>
                                            {!isActiveVersion && (
                                                <DropdownMenuItem onClick={handleRestoreVersion}>
                                                    <Check size={14} className="mr-2" />
                                                    Make Active Version
                                                </DropdownMenuItem>
                                            )}
                                            <DropdownMenuItem onClick={handleDeleteVersion}>
                                                <Trash2 size={14} className="mr-2" />
                                                Delete Version
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </div>

                                {/* Read-only version details */}
                                <div className="space-y-6">
                                    {/* Skill Name */}
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Name</Label>
                                        <div className="rounded p-3 text-sm">{currentGroup.name}</div>
                                    </div>

                                    {/* Type and Scope Badges */}
                                    <div className="flex flex-wrap gap-2">
                                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getTypeBadgeClass(currentGroup.type)}`}>{currentGroup.type === "learned" ? "Learned" : "Authored"}</span>
                                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${getScopeBadgeClass(currentGroup.scope)}`}>{currentGroup.scope}</span>
                                    </div>

                                    {/* Description */}
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Description</Label>
                                        <div className="rounded p-3 text-sm">{selectedVersion.description || "No description provided."}</div>
                                    </div>

                                    {/* Category */}
                                    {currentGroup.category && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Category</Label>
                                            <div className="rounded p-3 text-sm">{currentGroup.category}</div>
                                        </div>
                                    )}

                                    {/* Owner Agent */}
                                    {currentGroup.ownerAgentName && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Owner Agent</Label>
                                            <div className="rounded p-3 text-sm">{currentGroup.ownerAgentName}</div>
                                        </div>
                                    )}

                                    {/* Creation Reason */}
                                    {selectedVersion.creationReason && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Creation Reason</Label>
                                            <div className="rounded p-3 text-sm italic">{selectedVersion.creationReason}</div>
                                        </div>
                                    )}

                                    {/* Summary */}
                                    {selectedVersion.summary && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Summary</Label>
                                            <div className="rounded p-3 text-sm">{selectedVersion.summary}</div>
                                        </div>
                                    )}

                                    {/* Markdown Content */}
                                    {selectedVersion.markdownContent && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Content</Label>
                                            <div className="bg-muted/30 rounded p-4">
                                                <MarkdownHTMLConverter className="prose prose-sm dark:prose-invert max-w-none">{selectedVersion.markdownContent}</MarkdownHTMLConverter>
                                            </div>
                                        </div>
                                    )}

                                    {/* Steps */}
                                    {selectedVersion.steps && selectedVersion.steps.length > 0 && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Steps ({selectedVersion.steps.length})</Label>
                                            <div className="space-y-2">
                                                {selectedVersion.steps.map((step, index) => (
                                                    <div key={index} className="bg-muted/30 rounded p-3">
                                                        <div className="mb-1 flex items-center gap-2">
                                                            <span className="bg-primary/20 text-primary flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium">{step.stepNumber || index + 1}</span>
                                                            {step.toolName && <span className="text-muted-foreground font-mono text-xs">{step.toolName}</span>}
                                                        </div>
                                                        <div className="text-sm">{step.description || "No description"}</div>
                                                        {step.agentName && <div className="text-muted-foreground mt-1 text-xs">Agent: {step.agentName}</div>}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Agent Chain */}
                                    {selectedVersion.agentChain && selectedVersion.agentChain.length > 0 && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Agent Chain ({selectedVersion.agentChain.length})</Label>
                                            <div className="space-y-2">
                                                {selectedVersion.agentChain.map((node, index) => (
                                                    <div key={index} className="bg-muted/30 rounded p-3">
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-2">
                                                                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">{node.order}</span>
                                                                <span className="text-sm font-medium">{node.agentName}</span>
                                                            </div>
                                                            {node.role && <span className="text-muted-foreground text-xs">{node.role}</span>}
                                                        </div>
                                                        {node.toolsUsed && node.toolsUsed.length > 0 && (
                                                            <div className="mt-2 flex flex-wrap gap-1">
                                                                {node.toolsUsed.map((tool, toolIndex) => (
                                                                    <span key={toolIndex} className="bg-muted rounded px-1.5 py-0.5 font-mono text-xs">
                                                                        {tool}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Involved Agents */}
                                    {selectedVersion.involvedAgents && selectedVersion.involvedAgents.length > 0 && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Involved Agents</Label>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedVersion.involvedAgents.map((agent, index) => (
                                                    <span key={index} className="bg-primary/10 text-primary rounded-full px-2.5 py-0.5 text-xs font-medium">
                                                        {agent}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Source Task */}
                                    {selectedVersion.sourceTaskId && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Source Task</Label>
                                            <div className="rounded p-3 font-mono text-xs">{selectedVersion.sourceTaskId}</div>
                                        </div>
                                    )}

                                    {/* Complexity Score */}
                                    {selectedVersion.complexityScore !== undefined && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Complexity Score</Label>
                                            <div className="rounded p-3 text-sm">{selectedVersion.complexityScore}</div>
                                        </div>
                                    )}

                                    {/* Metadata */}
                                    <div className="border-t pt-4">
                                        <div className="text-muted-foreground text-xs">Created: {formatSkillDate(selectedVersion.createdAt)}</div>
                                        {selectedVersion.createdByUserId && <div className="text-muted-foreground text-xs">Created by: {selectedVersion.createdByUserId}</div>}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex h-full items-center justify-center">
                            <p className="text-muted-foreground">Select a version to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
