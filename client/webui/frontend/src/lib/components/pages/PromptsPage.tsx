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
import { EmptyState, Header } from '@/lib/components';
import { Button } from '@/lib/components/ui';
import { RefreshCcw } from 'lucide-react';
import { useChatContext } from '@/lib/hooks';

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
        setVersionHistoryGroup(null); 
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
        
        // Store prompt data in sessionStorage (including group for variable handling)
        const promptData = JSON.stringify({
            promptText,
            groupId: prompt.id,
            groupName: prompt.name
        });
        sessionStorage.setItem('pending-prompt-use', promptData);
        
        // Dispatch event to navigate to chat and use prompt
        window.dispatchEvent(new CustomEvent('use-prompt-in-chat', {
            detail: { promptText, groupId: prompt.id }
        }));
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
                    onSuccess={() => {
                        setShowBuilder(false);
                        setInitialMessage(null);
                        setEditingGroup(null);
                        setBuilderInitialMode('ai-assisted');
                        fetchPromptGroups();
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
                            setBuilderInitialMode('manual');
                            setShowBuilder(true);
                        }}
                        onAIAssisted={() => setShowGenerateDialog(true)}
                        onEdit={handleEdit}
                        onDelete={handleDeleteClick}
                        onViewVersions={setVersionHistoryGroup}
                        onUseInChat={handleUseInChat}
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
        </div>
    );
};