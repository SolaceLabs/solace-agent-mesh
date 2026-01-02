import React, { useCallback, useEffect, useRef, useState } from "react";
import { Check, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import type { Prompt, PromptGroup } from "@/lib/types/prompts";
import { Header } from "@/lib/components/header";
import { Button, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, Label } from "@/lib/components/ui";
import { formatPromptDate } from "@/lib/utils/promptUtils";
import { MessageBanner } from "@/lib/components/common";
import { getErrorMessage } from "@/lib/utils/api";
import { api } from "@/lib/api";
import { useChatContext } from "@/lib/hooks";

interface VersionHistoryPageProps {
    group: PromptGroup;
    onBack: () => void;
    onBackToPromptDetail: () => void;
    onEdit: (group: PromptGroup) => void;
    onDeleteAll: (id: string, name: string) => void;
    onRestoreVersion: (promptId: string) => Promise<void>;
}

export const VersionHistoryPage: React.FC<VersionHistoryPageProps> = ({ group, onBack, onEdit, onDeleteAll, onRestoreVersion }) => {
    const { addNotification, displayError } = useChatContext();
    const [versions, setVersions] = useState<Prompt[]>([]);
    const [selectedVersion, setSelectedVersion] = useState<Prompt | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [currentGroup, setCurrentGroup] = useState<PromptGroup>(group);
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
                const data = await api.webui.get(`/api/v1/prompts/groups/${group.id}/prompts`);
                setVersions(data);

                // Use a function update to access the current selectedVersion without adding it to dependencies
                setSelectedVersion(currentSelected => {
                    // If we have a _selectedVersionId from returning from edit, use that
                    if (group._selectedVersionId) {
                        const targetVersion = data.find((v: Prompt) => v.id === group._selectedVersionId);
                        if (targetVersion) {
                            return targetVersion;
                        }
                    }

                    // If preserving selection, try to keep the same version selected
                    if (preserveSelection && currentSelected) {
                        const stillExists = data.find((v: Prompt) => v.id === currentSelected.id);
                        if (stillExists) {
                            return stillExists;
                        } else {
                            // If the selected version was deleted, fall back to production
                            return data.find((v: Prompt) => v.id === group.productionPromptId) || data[0];
                        }
                    } else if (data.length > 0 && !hasInitializedRef.current) {
                        // Only set default selection on initial load
                        hasInitializedRef.current = true;
                        return data.find((v: Prompt) => v.id === group.productionPromptId) || data[0];
                    }
                    return currentSelected;
                });
            } catch (error) {
                console.error("Failed to fetch versions:", error);
            } finally {
                setIsLoading(false);
            }
        },
        [group.id, group.productionPromptId, group._selectedVersionId]
    );

    const fetchGroupData = useCallback(async () => {
        try {
            const data = await api.webui.get(`/api/v1/prompts/groups/${group.id}`);
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
        // Pass the group with the selected version as the production prompt
        // This allows editing any version, not just the active one
        // Use versioned metadata from the selected version, falling back to group values
        const groupWithSelectedVersion: PromptGroup = {
            ...currentGroup,
            // Override group metadata with version-specific values for editing
            name: selectedVersion?.name || currentGroup.name,
            description: selectedVersion?.description || currentGroup.description,
            category: selectedVersion?.category || currentGroup.category,
            command: selectedVersion?.command || currentGroup.command,
            productionPrompt: selectedVersion
                ? {
                      id: selectedVersion.id,
                      promptText: selectedVersion.promptText,
                      groupId: selectedVersion.groupId,
                      userId: selectedVersion.userId,
                      version: selectedVersion.version,
                      name: selectedVersion.name,
                      description: selectedVersion.description,
                      category: selectedVersion.category,
                      command: selectedVersion.command,
                      createdAt: selectedVersion.createdAt,
                      updatedAt: selectedVersion.updatedAt,
                  }
                : currentGroup.productionPrompt,
            // Store the actual production_prompt_id separately so we know if we're editing the active version
            _editingPromptId: selectedVersion?.id,
            _isEditingActiveVersion: selectedVersion?.id === currentGroup.productionPromptId,
            // Store which version should be selected when returning to version history
            _selectedVersionId: selectedVersion?.id,
        };
        onEdit(groupWithSelectedVersion);
    };

    const handleDeleteVersion = async () => {
        if (!selectedVersion) return;

        // Prevent deleting the active version
        if (selectedVersion.id === currentGroup.productionPromptId) {
            setShowDeleteActiveError(true);
            setTimeout(() => setShowDeleteActiveError(false), 5000);
            return;
        }

        try {
            await api.webui.delete(`/api/v1/prompts/${selectedVersion.id}`);
            addNotification("Version deleted successfully", "success");

            // Clear selection and refresh (don't preserve since we deleted it)
            setSelectedVersion(null);
            await fetchVersions(false);
        } catch (error) {
            displayError({ title: "Failed to Delete Version", error: getErrorMessage(error, "An unknown error occurred while deleting the version.") });
        }
    };

    const handleRestoreVersion = async () => {
        if (selectedVersion && selectedVersion.id !== currentGroup.productionPromptId) {
            await onRestoreVersion(selectedVersion.id);
            // Refresh group data to get updated production_prompt_id
            await fetchGroupData();
            // Refetch versions to update the UI, preserving the current selection
            await fetchVersions(true);
        }
    };

    const isActiveVersion = selectedVersion?.id === currentGroup.productionPromptId;

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <Header
                title={`Version History: ${currentGroup.name}`}
                breadcrumbs={[{ label: "Prompts", onClick: onBack }, { label: "Version History" }]}
                buttons={[
                    <DropdownMenu key="actions-menu">
                        <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
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
                                    const isActive = version.id === currentGroup.productionPromptId;
                                    const isSelected = selectedVersion?.id === version.id;

                                    return (
                                        <button data-testid={version.id} key={version.id} onClick={() => setSelectedVersion(version)} className={`w-full p-3 text-left transition-colors ${isSelected ? "bg-primary/5" : "hover:bg-muted/50"}`}>
                                            <div className="mb-1 flex items-center justify-between">
                                                <span className="text-sm font-medium">Version {version.version}</span>
                                                {isActive && <span className="rounded-full bg-[var(--color-success-w20)] px-2 py-0.5 text-xs text-[var(--color-success-wMain)]">Active</span>}
                                            </div>
                                            <span className="text-muted-foreground text-xs">{formatPromptDate(version.createdAt)}</span>
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

                                {/* Read-only version details - use versioned fields from selectedVersion, fallback to group */}
                                <div className="space-y-6">
                                    {/* Template Name */}
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Name</Label>
                                        <div className="rounded p-3 text-sm">{selectedVersion.name || currentGroup.name}</div>
                                    </div>

                                    {/* Description */}
                                    {(selectedVersion.description || currentGroup.description) && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Description</Label>
                                            <div className="rounded p-3 text-sm">{selectedVersion.description || currentGroup.description}</div>
                                        </div>
                                    )}

                                    {/* Chat Shortcut */}
                                    {(selectedVersion.command || currentGroup.command) && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Chat Shortcut</Label>
                                            <div className="rounded p-3 text-sm">
                                                <span className="text-primary font-mono">/{selectedVersion.command || currentGroup.command}</span>
                                            </div>
                                        </div>
                                    )}

                                    {/* Tag */}
                                    {(selectedVersion.category || currentGroup.category) && (
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Tag</Label>
                                            <div className="rounded p-3 text-sm">{selectedVersion.category || currentGroup.category}</div>
                                        </div>
                                    )}

                                    {/* Prompt Text */}
                                    <div className="space-y-2">
                                        <Label className="text-[var(--color-secondaryText-wMain)]">Content</Label>
                                        <div className="rounded p-3 font-mono text-sm break-words whitespace-pre-wrap">
                                            {selectedVersion.promptText.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                                if (part.match(/\{\{[^}]+\}\}/)) {
                                                    return (
                                                        <span key={index} className="bg-primary/20 text-primary rounded px-1 font-medium">
                                                            {part}
                                                        </span>
                                                    );
                                                }
                                                return <span key={index}>{part}</span>;
                                            })}
                                        </div>
                                    </div>

                                    {/* Metadata */}
                                    <div className="border-t pt-4">
                                        <div className="text-muted-foreground text-xs">Created: {formatPromptDate(selectedVersion.createdAt)}</div>
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
