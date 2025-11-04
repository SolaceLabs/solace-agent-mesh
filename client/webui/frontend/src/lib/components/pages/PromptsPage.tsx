/**
 * Main page for managing prompt library with AI-assisted builder
 */

import React, { useState, useEffect } from 'react';
import type { PromptGroup } from '@/lib/types/prompts';
import { PromptTemplateBuilder } from '@/lib/components/prompts/PromptTemplateBuilder';
import { PromptGroupForm } from '@/lib/components/prompts/PromptGroupForm';
import { PromptMeshCards } from '@/lib/components/prompts/PromptMeshCards';
import { VersionHistoryDialog } from '@/lib/components/prompts/VersionHistoryDialog';
import { PromptDeleteDialog } from '@/lib/components/prompts/PromptDeleteDialog';
import { GeneratePromptDialog } from '@/lib/components/prompts/GeneratePromptDialog';
import { EmptyState, Header } from '@/lib/components';
import { Button } from '@/lib/components/ui';
import { RefreshCcw } from 'lucide-react';
import { useChatContext } from '@/lib/hooks';

export const PromptsPage: React.FC = () => {
    const { addNotification } = useChatContext();
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showAIBuilder, setShowAIBuilder] = useState(false);
    const [showGenerateDialog, setShowGenerateDialog] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);
    const [showManualForm, setShowManualForm] = useState(false);
    const [editingGroup, setEditingGroup] = useState<PromptGroup | null>(null);
    const [versionHistoryGroup, setVersionHistoryGroup] = useState<PromptGroup | null>(null);
    const [deletingPrompt, setDeletingPrompt] = useState<{ id: string; name: string } | null>(null);

    // Fetch prompt groups
    const fetchPromptGroups = async () => {
        setIsLoading(true);
        try {
            const response = await fetch('/api/v1/prompts/groups/all', {
                credentials: 'include',
            });
            if (response.ok) {
                const data = await response.json();
                setPromptGroups(data);
            }
        } catch (error) {
            console.error('Failed to fetch prompt groups:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchPromptGroups();
    }, []);

    // Delete prompt group
    const handleDeleteClick = (id: string, name: string) => {
        setDeletingPrompt({ id, name });
    };

    const handleDeleteConfirm = async () => {
        if (!deletingPrompt) return;
        
        try {
            const response = await fetch(`/api/v1/prompts/groups/${deletingPrompt.id}`, {
                method: 'DELETE',
                credentials: 'include',
            });
            if (response.ok) {
                fetchPromptGroups();
                setDeletingPrompt(null);
            }
        } catch (error) {
            console.error('Failed to delete prompt:', error);
        }
    };

    // Handle edit
    const handleEdit = (group: PromptGroup) => {
        setEditingGroup(group);
        setShowManualForm(true);
    };

    // Handle update
    const handleUpdate = async (data: any) => {
        if (!editingGroup) return;
        
        try {
            const response = await fetch(`/api/v1/prompts/groups/${editingGroup.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data),
            });
            
            if (response.ok) {
                setEditingGroup(null);
                setShowManualForm(false);
                fetchPromptGroups();
                addNotification('Prompt updated successfully', 'success');
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to update prompt';
                addNotification(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Failed to update prompt:', error);
            addNotification('Network error: Failed to update prompt', 'error');
        }
    };

    // Handle create
    const handleCreate = async (data: any) => {
        try {
            const response = await fetch('/api/v1/prompts/groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(data),
            });
            
            if (response.ok) {
                setShowManualForm(false);
                fetchPromptGroups();
                addNotification('Prompt created successfully', 'success');
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to create prompt';
                addNotification(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Failed to create prompt:', error);
            addNotification('Network error: Failed to create prompt', 'error');
        }
    };

    // Handle restore version
    const handleRestoreVersion = async (promptId: string) => {
        try {
            const response = await fetch(`/api/v1/prompts/${promptId}/make-production`, {
                method: 'PATCH',
                credentials: 'include',
            });
            
            if (response.ok) {
                setVersionHistoryGroup(null);
                fetchPromptGroups();
                addNotification('Version restored successfully', 'success');
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to restore version';
                addNotification(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Failed to restore version:', error);
            addNotification('Failed to restore version', 'error');
        }
    };

    // Handle AI builder generation
    const handleGeneratePrompt = (taskDescription: string) => {
        setInitialMessage(taskDescription);
        setShowGenerateDialog(false);
        setShowAIBuilder(true);
    };

    // Show AI Builder as full page view
    if (showAIBuilder) {
        return (
            <PromptTemplateBuilder
                onBack={() => {
                    setShowAIBuilder(false);
                    setInitialMessage(null);
                }}
                onSuccess={() => {
                    setShowAIBuilder(false);
                    setInitialMessage(null);
                    fetchPromptGroups();
                }}
                initialMessage={initialMessage}
            />
        );
    }

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Prompts"
                buttons={[
                    <Button
                        data-testid="refreshPrompts"
                        disabled={isLoading}
                        variant="ghost"
                        title="Refresh Prompts"
                        onClick={() => fetchPromptGroups()}
                    >
                        <RefreshCcw className="size-4" />
                        Refresh Prompts
                    </Button>,
                ]}
            />

            {isLoading ? (
                <EmptyState title="Loading prompts..." variant="loading" />
            ) : (
                <div className="relative flex-1 p-4">
                    <PromptMeshCards
                        prompts={promptGroups}
                        onManualCreate={() => {
                            setEditingGroup(null);
                            setShowManualForm(true);
                        }}
                        onAIAssisted={() => setShowGenerateDialog(true)}
                        onEdit={handleEdit}
                        onDelete={handleDeleteClick}
                        onViewVersions={setVersionHistoryGroup}
                    />
                </div>
            )}

            {/* Manual Form Dialog */}
            {showManualForm && (
                <PromptGroupForm
                    group={editingGroup}
                    onSubmit={editingGroup ? handleUpdate : handleCreate}
                    onClose={() => {
                        setShowManualForm(false);
                        setEditingGroup(null);
                    }}
                />
            )}

            {/* Version History Dialog */}
            {versionHistoryGroup && (
                <VersionHistoryDialog
                    group={versionHistoryGroup}
                    onClose={() => setVersionHistoryGroup(null)}
                    onRestore={handleRestoreVersion}
                />
            )}

            {/* Delete Confirmation Dialog */}
            {deletingPrompt && (
                <PromptDeleteDialog
                    isOpen={true}
                    onClose={() => setDeletingPrompt(null)}
                    onConfirm={handleDeleteConfirm}
                    promptName={deletingPrompt.name}
                />
            )}

            {/* Generate Prompt Dialog */}
            <GeneratePromptDialog
                isOpen={showGenerateDialog}
                onClose={() => setShowGenerateDialog(false)}
                onGenerate={handleGeneratePrompt}
            />
        </div>
    );
};