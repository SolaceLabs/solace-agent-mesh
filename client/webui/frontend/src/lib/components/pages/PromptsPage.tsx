/**
 * Main page for managing prompt library with AI-assisted builder
 */

import React, { useState, useEffect } from 'react';
import type { PromptGroup } from '@/lib/types/prompts';
import { PromptTemplateBuilder } from '@/lib/components/prompts/PromptTemplateBuilder';
import { PromptMeshCards } from '@/lib/components/prompts/PromptMeshCards';
import { VersionHistoryPage } from '@/lib/components/prompts/VersionHistoryPage';
import { PromptDeleteDialog } from '@/lib/components/prompts/PromptDeleteDialog';
import { GeneratePromptDialog } from '@/lib/components/prompts/GeneratePromptDialog';
import { VariableDialog } from '@/lib/components/chat/VariableDialog';
import { EmptyState, Header } from '@/lib/components';
import { Button } from '@/lib/components/ui';
import { RefreshCcw } from 'lucide-react';
import { useChatContext } from '@/lib/hooks';
import { detectVariables } from '@/lib/utils/promptUtils';

export const PromptsPage: React.FC = () => {
    const { addNotification } = useChatContext();
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showBuilder, setShowBuilder] = useState(false);
    const [showGenerateDialog, setShowGenerateDialog] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);
    const [editingGroup, setEditingGroup] = useState<PromptGroup | null>(null);
    const [builderInitialMode, setBuilderInitialMode] = useState<'manual' | 'ai-assisted'>('ai-assisted');
    const [versionHistoryGroup, setVersionHistoryGroup] = useState<PromptGroup | null>(null);
    const [deletingPrompt, setDeletingPrompt] = useState<{ id: string; name: string } | null>(null);
    const [newlyCreatedPromptId, setNewlyCreatedPromptId] = useState<string | null>(null);
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [pendingPromptGroup, setPendingPromptGroup] = useState<PromptGroup | null>(null);

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
        
        const pendingContext = sessionStorage.getItem('pending-template-context');
        if (pendingContext) {
            sessionStorage.removeItem('pending-template-context');
            setInitialMessage(pendingContext);
            setEditingGroup(null);
            setBuilderInitialMode('ai-assisted');
            setShowBuilder(true);
        }
    }, []);

    useEffect(() => {
        const handleCreateTemplateFromSession = (event: Event) => {
            const customEvent = event as CustomEvent;
            const { initialMessage: message } = customEvent.detail;
            
            setInitialMessage(message);
            setEditingGroup(null);
            setBuilderInitialMode('ai-assisted');
            setShowBuilder(true);
            setVersionHistoryGroup(null); 
        };

        window.addEventListener('create-template-from-session', handleCreateTemplateFromSession);
        return () => {
            window.removeEventListener('create-template-from-session', handleCreateTemplateFromSession);
        };
    }, []);

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
                if (versionHistoryGroup?.id === deletingPrompt.id) {
                    setVersionHistoryGroup(null);
                }
                await fetchPromptGroups();
                setDeletingPrompt(null);
                addNotification('Prompt deleted successfully', 'success');
            } else {
                setDeletingPrompt(null);
                addNotification('Failed to delete prompt', 'error');
            }
        } catch (error) {
            console.error('Failed to delete prompt:', error);
            setDeletingPrompt(null);
            addNotification('Failed to delete prompt', 'error');
        }
    };

    const handleEdit = (group: PromptGroup) => {
        // Don't clear versionHistoryGroup - we'll return to it after editing
        setEditingGroup(group);
        setBuilderInitialMode('manual');
        setShowBuilder(true);
    };

    const handleRestoreVersion = async (promptId: string) => {
        try {
            const response = await fetch(`/api/v1/prompts/${promptId}/make-production`, {
                method: 'PATCH',
                credentials: 'include',
            });
            
            if (response.ok) {
                fetchPromptGroups();
                addNotification('Version made active successfully', 'success');
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || 'Failed to make version active';
                addNotification(errorMessage, 'error');
            }
        } catch (error) {
            console.error('Failed to make version active:', error);
            addNotification('Failed to make version active', 'error');
        }
    };

    // Handle AI builder generation
    const handleGeneratePrompt = (taskDescription: string) => {
        setInitialMessage(taskDescription);
        setShowGenerateDialog(false);
        setEditingGroup(null);
        setBuilderInitialMode('ai-assisted');
        setShowBuilder(true);
    };

    // Handle use in chat
    const handleUseInChat = (prompt: PromptGroup) => {
        const promptText = prompt.production_prompt?.prompt_text || '';
        
        // Check if prompt has variables
        const variables = detectVariables(promptText);
        const hasVariables = variables.length > 0;
        
        if (hasVariables) {
            // Show variable dialog on prompts page
            setPendingPromptGroup(prompt);
            setShowVariableDialog(true);
        } else {
            // No variables - navigate directly to chat
            const promptData = JSON.stringify({
                promptText,
                groupId: prompt.id,
                groupName: prompt.name
            });
            sessionStorage.setItem('pending-prompt-use', promptData);
            
            window.dispatchEvent(new CustomEvent('use-prompt-in-chat', {
                detail: { promptText, groupId: prompt.id }
            }));
        }
    };

    // Handle variable dialog submission
    const handleVariableSubmit = (processedPrompt: string) => {
        if (!pendingPromptGroup) return;
        
        // Store the processed prompt in sessionStorage
        const promptData = JSON.stringify({
            promptText: processedPrompt,
            groupId: pendingPromptGroup.id,
            groupName: pendingPromptGroup.name
        });
        sessionStorage.setItem('pending-prompt-use', promptData);
        
        // Navigate to chat
        window.dispatchEvent(new CustomEvent('use-prompt-in-chat', {
            detail: { promptText: processedPrompt, groupId: pendingPromptGroup.id }
        }));
        
        // Clean up
        setShowVariableDialog(false);
        setPendingPromptGroup(null);
    };

    const handleTogglePin = async (id: string, currentStatus: boolean) => {
        try {
            // Optimistic update
            setPromptGroups(prev => prev.map(p =>
                p.id === id ? { ...p, is_pinned: !currentStatus } : p
            ));

            const response = await fetch(`/api/v1/prompts/groups/${id}/pin`, {
                method: 'PATCH',
                credentials: 'include',
            });

            if (!response.ok) {
                // Revert on error
                setPromptGroups(prev => prev.map(p =>
                    p.id === id ? { ...p, is_pinned: currentStatus } : p
                ));
                addNotification('Failed to update pin status', 'error');
            } else {
                addNotification(
                    currentStatus ? 'Template unpinned' : 'Template pinned',
                    'success'
                );
            }
        } catch (error) {
            // Revert on error
            setPromptGroups(prev => prev.map(p =>
                p.id === id ? { ...p, is_pinned: currentStatus } : p
            ));
            console.error('Failed to toggle pin:', error);
            addNotification('Failed to update pin status', 'error');
        }
    };

    if (showBuilder) {
        return (
            <>
                <PromptTemplateBuilder
                    onBack={() => {
                        setShowBuilder(false);
                        setInitialMessage(null);
                        setEditingGroup(null);
                    }}
                    onSuccess={async (createdNewVersion?: boolean, createdPromptId?: string | null) => {
                        setShowBuilder(false);
                        setInitialMessage(null);
                        const wasEditingGroup = editingGroup;
                        setEditingGroup(null);
                        setBuilderInitialMode('ai-assisted');
                        
                        // Store the newly created/edited prompt ID for auto-selection
                        if (createdPromptId) {
                            setNewlyCreatedPromptId(createdPromptId);
                        }
                        
                        await fetchPromptGroups();
                        
                        // If returning to Version History, refresh the group data
                        if (versionHistoryGroup) {
                            try {
                                const response = await fetch(`/api/v1/prompts/groups/${versionHistoryGroup.id}`, {
                                    credentials: 'include',
                                });
                                if (response.ok) {
                                    const updatedGroup = await response.json();
                                    // If a new version was created, select the new production version
                                    // Otherwise, preserve the previously selected version
                                    setVersionHistoryGroup({
                                        ...updatedGroup,
                                        _selectedVersionId: createdNewVersion
                                            ? updatedGroup.production_prompt_id
                                            : wasEditingGroup?._selectedVersionId,
                                    });
                                }
                            } catch (error) {
                                console.error('Failed to refresh version history group:', error);
                            }
                        }
                    }}
                    initialMessage={initialMessage}
                    editingGroup={editingGroup}
                    isEditing={!!editingGroup}
                    initialMode={builderInitialMode}
                />
                
                {/* Dialogs rendered globally */}
                {deletingPrompt && (
                    <PromptDeleteDialog
                        key={`delete-${deletingPrompt.id}`}
                        isOpen={true}
                        onClose={() => setDeletingPrompt(null)}
                        onConfirm={handleDeleteConfirm}
                        promptName={deletingPrompt.name}
                    />
                )}
                <GeneratePromptDialog
                    isOpen={showGenerateDialog}
                    onClose={() => setShowGenerateDialog(false)}
                    onGenerate={handleGeneratePrompt}
                />
            </>
        );
    }

    // Show Version History as full page view
    if (versionHistoryGroup) {
        return (
            <>
                <VersionHistoryPage
                    group={versionHistoryGroup}
                    onBack={() => setVersionHistoryGroup(null)}
                    onBackToPromptDetail={() => {
                        setVersionHistoryGroup(null);
                    }}
                    onEdit={handleEdit}
                    onDeleteAll={handleDeleteClick}
                    onRestoreVersion={handleRestoreVersion}
                />
                
                {/* Dialogs rendered globally */}
                {deletingPrompt && (
                    <PromptDeleteDialog
                        key={`delete-${deletingPrompt.id}`}
                        isOpen={true}
                        onClose={() => setDeletingPrompt(null)}
                        onConfirm={handleDeleteConfirm}
                        promptName={deletingPrompt.name}
                    />
                )}
            </>
        );
    }

    // Main prompts view
    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Prompts"
                buttons={promptGroups.length > 0 ? [
                    <Button
                        data-testid="refreshPrompts"
                        disabled={isLoading}
                        variant="ghost"
                        tooltip="Refresh Prompts"
                        onClick={() => fetchPromptGroups()}
                    >
                        <RefreshCcw className="size-4" />
                        Refresh Prompts
                    </Button>,
                ] : []}
            />

            {isLoading ? (
                <EmptyState title="Loading prompts..." variant="loading" />
            ) : (
                <div className="relative flex-1 p-4">
                    <PromptMeshCards
                        prompts={promptGroups}
                        onManualCreate={() => {
                            setEditingGroup(null);
                            setBuilderInitialMode('manual');
                            setShowBuilder(true);
                        }}
                        onAIAssisted={() => setShowGenerateDialog(true)}
                        onEdit={handleEdit}
                        onDelete={handleDeleteClick}
                        onViewVersions={setVersionHistoryGroup}
                        onUseInChat={handleUseInChat}
                        onTogglePin={handleTogglePin}
                        newlyCreatedPromptId={newlyCreatedPromptId}
                    />
                </div>
            )}

            {/* Delete Confirmation Dialog */}
            {deletingPrompt && (
                <PromptDeleteDialog
                    key={`delete-${deletingPrompt.id}`}
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

            {/* Variable Dialog for "Use in Chat" */}
            {showVariableDialog && pendingPromptGroup && (
                <VariableDialog
                    group={pendingPromptGroup}
                    onSubmit={handleVariableSubmit}
                    onClose={() => {
                        setShowVariableDialog(false);
                        setPendingPromptGroup(null);
                    }}
                />
            )}
        </div>
    );
};