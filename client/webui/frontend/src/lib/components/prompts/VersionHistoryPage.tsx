import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Pencil, Trash2, MoreHorizontal, Check } from 'lucide-react';
import type { PromptGroup, Prompt } from '@/lib/types/prompts';
import { Header } from '@/lib/components/header';
import { Button, Label } from '@/lib/components/ui';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/lib/components/ui';
import { formatPromptDate } from '@/lib/utils/promptUtils';
import { useChatContext } from '@/lib/hooks';
import { MessageBanner } from '@/lib/components/common';

interface VersionHistoryPageProps {
    group: PromptGroup;
    onBack: () => void;
    onBackToPromptDetail: () => void;
    onEdit: (group: PromptGroup) => void;
    onDeleteAll: (id: string, name: string) => void;
    onRestoreVersion: (promptId: string) => Promise<void>;
}

export const VersionHistoryPage: React.FC<VersionHistoryPageProps> = ({
    group,
    onBack,
    onEdit,
    onDeleteAll,
    onRestoreVersion,
}) => {
    const { addNotification } = useChatContext();
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

    const fetchVersions = useCallback(async (preserveSelection = false) => {
        setIsLoading(true);
        try {
            const response = await fetch(`/api/v1/prompts/groups/${group.id}/prompts`, {
                credentials: 'include',
            });
            
            if (response.ok) {
                const data = await response.json();
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
                            return data.find((v: Prompt) => v.id === group.production_prompt_id) || data[0];
                        }
                    } else if (data.length > 0 && !hasInitializedRef.current) {
                        // Only set default selection on initial load
                        hasInitializedRef.current = true;
                        return data.find((v: Prompt) => v.id === group.production_prompt_id) || data[0];
                    }
                    return currentSelected;
                });
            }
        } catch (error) {
            console.error('Failed to fetch versions:', error);
        } finally {
            setIsLoading(false);
        }
    }, [group.id, group.production_prompt_id, group._selectedVersionId]);

    const fetchGroupData = useCallback(async () => {
        try {
            const response = await fetch(`/api/v1/prompts/groups/${group.id}`, {
                credentials: 'include',
            });
            
            if (response.ok) {
                const data = await response.json();
                setCurrentGroup(data);
            }
        } catch (error) {
            console.error('Failed to fetch group data:', error);
        }
    }, [group.id]);

    useEffect(() => {
        // Preserve selection when the component updates (e.g., after editing)
        fetchVersions(true);
    }, [fetchVersions]);

    const handleEditVersion = () => {
        // Pass the group with the selected version as the production prompt
        // This allows editing any version, not just the active one
        const groupWithSelectedVersion: PromptGroup = {
            ...currentGroup,
            production_prompt: selectedVersion ? {
                id: selectedVersion.id,
                prompt_text: selectedVersion.prompt_text,
                group_id: selectedVersion.group_id,
                user_id: selectedVersion.user_id,
                version: selectedVersion.version,
                created_at: selectedVersion.created_at,
                updated_at: selectedVersion.updated_at,
            } : currentGroup.production_prompt,
            // Store the actual production_prompt_id separately so we know if we're editing the active version
            _editingPromptId: selectedVersion?.id,
            _isEditingActiveVersion: selectedVersion?.id === currentGroup.production_prompt_id,
            // Store which version should be selected when returning to version history
            _selectedVersionId: selectedVersion?.id,
        };
        onEdit(groupWithSelectedVersion);
    };

    const handleDeleteVersion = async () => {
        if (!selectedVersion) return;
        
        // Prevent deleting the active version
        if (selectedVersion.id === currentGroup.production_prompt_id) {
            setShowDeleteActiveError(true);
            setTimeout(() => setShowDeleteActiveError(false), 5000);
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/prompts/${selectedVersion.id}`, {
                method: 'DELETE',
                credentials: 'include',
            });
            
            if (response.ok) {
                addNotification('Version deleted successfully', 'success');
                // Clear selection and refresh (don't preserve since we deleted it)
                setSelectedVersion(null);
                await fetchVersions(false);
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to delete version';
                addNotification(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Failed to delete version:', error);
            addNotification('Failed to delete version', 'error');
        }
    };

    const handleRestoreVersion = async () => {
        if (selectedVersion && selectedVersion.id !== currentGroup.production_prompt_id) {
            await onRestoreVersion(selectedVersion.id);
            // Refresh group data to get updated production_prompt_id
            await fetchGroupData();
            // Refetch versions to update the UI, preserving the current selection
            await fetchVersions(true);
        }
    };

    const isActiveVersion = selectedVersion?.id === currentGroup.production_prompt_id;

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <Header
                title={`Version History: ${currentGroup.name}`}
                breadcrumbs={[
                    { label: "Prompts", onClick: onBack },
                    { label: "Version History" }
                ]}
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
                    </DropdownMenu>
                ]}
            />

            {/* Error Banner */}
            {showDeleteActiveError && (
                <MessageBanner
                    variant="error"
                    message="Cannot delete the active version. Please make another version active first."
                />
            )}

            {/* Content */}
            <div className="flex flex-1 min-h-0">
                {/* Left Sidebar - Version List */}
                <div className="w-[300px] border-r overflow-y-auto">
                    <div className="p-4">
                        <h3 className="text-sm font-semibold text-muted-foreground mb-3">Versions</h3>
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {versions.map((version) => {
                                    const isActive = version.id === currentGroup.production_prompt_id;
                                    const isSelected = selectedVersion?.id === version.id;
                                    
                                    return (
                                        <button
                                            key={version.id}
                                            onClick={() => setSelectedVersion(version)}
                                            className={`w-full text-left p-3 transition-colors ${
                                                isSelected
                                                    ? 'bg-primary/5'
                                                    : 'hover:bg-muted/50'
                                            }`}
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="font-medium text-sm">
                                                    Version {version.version}
                                                </span>
                                                {isActive && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-success-w20)] text-[var(--color-success-wMain)]">
                                                        Active
                                                    </span>
                                                )}
                                            </div>
                                            <span className="text-xs text-muted-foreground">
                                                {formatPromptDate(version.created_at)}
                                            </span>
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
                            <div className="max-w-4xl mx-auto space-y-6">
                                {/* Header with actions */}
                                <div className="flex items-center justify-between">
                                    <h2 className="text-lg font-semibold">
                                        Version {selectedVersion.version} Details
                                    </h2>
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
                                        {/* Template Name */}
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Name</Label>
                                            <div className="text-sm p-3 rounded">
                                                {currentGroup.name}
                                            </div>
                                        </div>

                                        {/* Description */}
                                        {currentGroup.description && (
                                            <div className="space-y-2">
                                                <Label className="text-[var(--color-secondaryText-wMain)]">Description</Label>
                                                <div className="text-sm p-3 rounded">
                                                    {currentGroup.description}
                                                </div>
                                            </div>
                                        )}

                                        {/* Chat Shortcut */}
                                        {currentGroup.command && (
                                            <div className="space-y-2">
                                                <Label className="text-[var(--color-secondaryText-wMain)]">Chat Shortcut</Label>
                                                <div className="text-sm p-3 rounded">
                                                    <span className="font-mono text-primary">/{currentGroup.command}</span>
                                                </div>
                                            </div>
                                        )}

                                        {/* Tag */}
                                        {currentGroup.category && (
                                            <div className="space-y-2">
                                                <Label className="text-[var(--color-secondaryText-wMain)]">Tag</Label>
                                                <div className="text-sm p-3 rounded">
                                                    {currentGroup.category}
                                                </div>
                                            </div>
                                        )}

                                        {/* Prompt Text */}
                                        <div className="space-y-2">
                                            <Label className="text-[var(--color-secondaryText-wMain)]">Content</Label>
                                            <div className="p-3 rounded text-sm font-mono whitespace-pre-wrap break-words">
                                                {selectedVersion.prompt_text.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                                    if (part.match(/\{\{[^}]+\}\}/)) {
                                                        return (
                                                            <span key={index} className="bg-primary/20 text-primary font-medium px-1 rounded">
                                                                {part}
                                                            </span>
                                                        );
                                                    }
                                                    return <span key={index}>{part}</span>;
                                                })}
                                            </div>
                                        </div>

                                        {/* Metadata */}
                                        <div className="pt-4 border-t">
                                            <div className="text-xs text-muted-foreground">
                                                Created: {formatPromptDate(selectedVersion.created_at)}
                                            </div>
                                        </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-muted-foreground">Select a version to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};