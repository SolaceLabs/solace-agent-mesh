import React, { useState, useEffect } from "react";
import { useLoaderData, useNavigate, useLocation } from "react-router-dom";
import { RefreshCcw, Download } from "lucide-react";

import { useChatContext } from "@/lib/hooks";
import type { PromptGroup } from "@/lib/types/prompts";
import { Button, EmptyState, Header, VariableDialog } from "@/lib/components";
import { GeneratePromptDialog, PromptCards, PromptDeleteDialog, PromptTemplateBuilder, VersionHistoryPage, PromptImportDialog } from "@/lib/components/prompts";
import { authenticatedFetch, detectVariables } from "@/lib/utils";

/**
 * Main page for managing prompt library with AI-assisted builder
 */
export const PromptsPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const loaderData = useLoaderData<{ promptId?: string; view?: string; mode?: string }>();

    const { addNotification } = useChatContext();
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showBuilder, setShowBuilder] = useState(false);
    const [showGenerateDialog, setShowGenerateDialog] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);
    const [editingGroup, setEditingGroup] = useState<PromptGroup | null>(null);
    const [builderInitialMode, setBuilderInitialMode] = useState<"manual" | "ai-assisted">("ai-assisted");
    const [versionHistoryGroup, setVersionHistoryGroup] = useState<PromptGroup | null>(null);
    const [deletingPrompt, setDeletingPrompt] = useState<{ id: string; name: string } | null>(null);
    const [newlyCreatedPromptId, setNewlyCreatedPromptId] = useState<string | null>(null);
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [pendingPromptGroup, setPendingPromptGroup] = useState<PromptGroup | null>(null);
    const [showImportDialog, setShowImportDialog] = useState(false);

    // Fetch prompt groups
    const fetchPromptGroups = async () => {
        setIsLoading(true);
        try {
            const response = await authenticatedFetch("/api/v1/prompts/groups/all", {
                credentials: "include",
            });
            if (response.ok) {
                const data = await response.json();
                setPromptGroups(data);
            }
        } catch (error) {
            console.error("Failed to fetch prompt groups:", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchPromptGroups();
    }, []);

    // Handle route-based views from loaderData
    useEffect(() => {
        if (loaderData?.view === "builder") {
            // Show builder based on mode
            if (loaderData.mode === "edit" && loaderData.promptId) {
                // Load the prompt group for editing
                const loadPromptForEdit = async () => {
                    try {
                        const response = await authenticatedFetch(`/api/v1/prompts/groups/${loaderData.promptId}`);
                        if (response.ok) {
                            const group = await response.json();
                            setEditingGroup(group);
                            setBuilderInitialMode("manual");
                            setShowBuilder(true);
                        }
                    } catch (error) {
                        console.error("Failed to load prompt for editing:", error);
                    }
                };
                loadPromptForEdit();
            } else {
                // New prompt (manual or AI-assisted)
                setEditingGroup(null);
                const mode = loaderData.mode === "ai-assisted" ? "ai-assisted" : "manual";
                setBuilderInitialMode(mode);

                // Check for pending task description from router state
                if (mode === "ai-assisted" && location.state?.taskDescription) {
                    setInitialMessage(location.state.taskDescription);
                }

                setShowBuilder(true);
            }
        } else if (loaderData?.view === "versions" && loaderData.promptId) {
            // Load the prompt group for version history
            const loadPromptGroup = async () => {
                try {
                    const response = await authenticatedFetch(`/api/v1/prompts/groups/${loaderData.promptId}`);
                    if (response.ok) {
                        const group = await response.json();
                        setVersionHistoryGroup(group);
                    }
                } catch (error) {
                    console.error("Failed to load prompt group:", error);
                }
            };
            loadPromptGroup();
        } else {
            // Main list view - reset states
            setShowBuilder(false);
            setVersionHistoryGroup(null);
            setEditingGroup(null);
        }
    }, [loaderData, location.state?.taskDescription]);

    const handleDeleteClick = (id: string, name: string) => {
        setDeletingPrompt({ id, name });
    };

    const handleDeleteConfirm = async () => {
        if (!deletingPrompt) return;

        try {
            const response = await authenticatedFetch(`/api/v1/prompts/groups/${deletingPrompt.id}`, {
                method: "DELETE",
            });
            if (response.ok) {
                if (versionHistoryGroup?.id === deletingPrompt.id) {
                    setVersionHistoryGroup(null);
                }
                await fetchPromptGroups();
                setDeletingPrompt(null);
                addNotification("Prompt deleted successfully", "success");
            } else {
                setDeletingPrompt(null);
                addNotification("Failed to delete prompt", "error");
            }
        } catch (error) {
            console.error("Failed to delete prompt:", error);
            setDeletingPrompt(null);
            addNotification("Failed to delete prompt", "error");
        }
    };

    const handleEdit = (group: PromptGroup) => {
        navigate(`/prompts/${group.id}/edit`);
    };

    const handleRestoreVersion = async (promptId: string) => {
        try {
            const response = await authenticatedFetch(`/api/v1/prompts/${promptId}/make-production`, {
                method: "PATCH",
            });

            if (response.ok) {
                fetchPromptGroups();
                addNotification("Version made active successfully", "success");
            } else {
                const error = await response.json();
                const errorMessage = error.message || error.detail || "Failed to make version active";
                addNotification(errorMessage, "error");
            }
        } catch (error) {
            console.error("Failed to make version active:", error);
            addNotification("Failed to make version active", "error");
        }
    };

    // Handle AI builder generation
    const handleGeneratePrompt = (taskDescription: string) => {
        setShowGenerateDialog(false);
        navigate("/prompts/new?mode=ai-assisted", {
            state: { taskDescription },
        });
    };

    // Handle use in chat
    const handleUseInChat = (prompt: PromptGroup) => {
        const promptText = prompt.production_prompt?.prompt_text || "";

        // Check if prompt has variables
        const variables = detectVariables(promptText);
        const hasVariables = variables.length > 0;

        if (hasVariables) {
            // Show variable dialog on prompts page
            setPendingPromptGroup(prompt);
            setShowVariableDialog(true);
        } else {
            // No variables - navigate directly to chat
            navigate("/chat", {
                state: {
                    promptText,
                    groupId: prompt.id,
                    groupName: prompt.name,
                },
            });
        }
    };

    // Handle variable dialog submission
    const handleVariableSubmit = (processedPrompt: string) => {
        if (!pendingPromptGroup) return;

        // Navigate to chat with prompt data
        navigate("/chat", {
            state: {
                promptText: processedPrompt,
                groupId: pendingPromptGroup.id,
                groupName: pendingPromptGroup.name,
            },
        });

        // Clean up
        setShowVariableDialog(false);
        setPendingPromptGroup(null);
    };

    const handleTogglePin = async (id: string, currentStatus: boolean) => {
        try {
            // Optimistic update
            setPromptGroups(prev => prev.map(p => (p.id === id ? { ...p, is_pinned: !currentStatus } : p)));

            const response = await authenticatedFetch(`/api/v1/prompts/groups/${id}/pin`, {
                method: "PATCH",
                credentials: "include",
            });

            if (!response.ok) {
                // Revert on error
                setPromptGroups(prev => prev.map(p => (p.id === id ? { ...p, is_pinned: currentStatus } : p)));
                addNotification("Failed to update pin status", "error");
            } else {
                addNotification(currentStatus ? "Template unpinned" : "Template pinned", "success");
            }
        } catch (error) {
            // Revert on error
            setPromptGroups(prev => prev.map(p => (p.id === id ? { ...p, is_pinned: currentStatus } : p)));
            console.error("Failed to toggle pin:", error);
            addNotification("Failed to update pin status", "error");
        }
    };

    // Handle export
    const handleExport = async (prompt: PromptGroup) => {
        try {
            const response = await authenticatedFetch(`/api/v1/prompts/groups/${prompt.id}/export`, {
                credentials: "include",
            });

            if (response.ok) {
                const exportData = await response.json();

                // Create a blob and trigger download
                const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `prompt-${prompt.name.replace(/[^a-z0-9]/gi, "-").toLowerCase()}-${Date.now()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                addNotification("Prompt exported successfully", "success");
            } else {
                const error = await response.json();
                const errorMessage = error.detail || "Failed to export prompt";
                addNotification(errorMessage, "error");
            }
        } catch (error) {
            console.error("Failed to export prompt:", error);
            addNotification("Failed to export prompt", "error");
        }
    };

    // Handle import
    const handleImport = async (importData: PromptImportData, options: { preserve_command: boolean; preserve_category: boolean }) => {
        try {
            const response = await authenticatedFetch("/api/v1/prompts/import", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: "include",
                body: JSON.stringify({
                    prompt_data: importData,
                    options,
                }),
            });

            if (response.ok) {
                const result = await response.json();

                // Show warnings if any
                if (result.warnings && result.warnings.length > 0) {
                    result.warnings.forEach((warning: string) => {
                        addNotification(warning, "info");
                    });
                }

                // Navigate back to prompts page
                setShowBuilder(false);
                setShowImportDialog(false);
                setInitialMessage(null);
                setEditingGroup(null);

                // Refresh prompts and select the newly imported one
                await fetchPromptGroups();
                setNewlyCreatedPromptId(result.prompt_group_id);

                addNotification("Prompt imported successfully", "success");
            } else {
                const error = await response.json();
                const errorMessage = error.detail || "Failed to import prompt";
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error("Failed to import prompt:", error);
            throw error; // Re-throw to let dialog handle it
        }
    };

    // Type for import data
    interface PromptImportData {
        version: string;
        exported_at: number;
        prompt: {
            name: string;
            description?: string;
            category?: string;
            command?: string;
            prompt_text: string;
            metadata?: {
                author_name?: string;
                original_version: number;
                original_created_at: number;
            };
        };
    }

    if (showBuilder) {
        return (
            <>
                <PromptTemplateBuilder
                    onBack={() => {
                        navigate("/prompts");
                    }}
                    onSuccess={async (createdPromptId?: string | null) => {
                        // Store the newly created/edited prompt ID for auto-selection
                        if (createdPromptId) {
                            setNewlyCreatedPromptId(createdPromptId);
                        }

                        await fetchPromptGroups();

                        // Navigate back to prompts list
                        navigate("/prompts");
                    }}
                    initialMessage={initialMessage}
                    editingGroup={editingGroup}
                    isEditing={!!editingGroup}
                    initialMode={builderInitialMode}
                />

                {/* Dialogs rendered globally */}
                {deletingPrompt && <PromptDeleteDialog key={`delete-${deletingPrompt.id}`} isOpen={true} onClose={() => setDeletingPrompt(null)} onConfirm={handleDeleteConfirm} promptName={deletingPrompt.name} />}
                <GeneratePromptDialog isOpen={showGenerateDialog} onClose={() => setShowGenerateDialog(false)} onGenerate={handleGeneratePrompt} />
            </>
        );
    }

    // Show Version History as full page view
    if (versionHistoryGroup) {
        return (
            <>
                <VersionHistoryPage group={versionHistoryGroup} onBack={() => navigate("/prompts")} onBackToPromptDetail={() => navigate("/prompts")} onEdit={handleEdit} onDeleteAll={handleDeleteClick} onRestoreVersion={handleRestoreVersion} />

                {/* Dialogs rendered globally */}
                {deletingPrompt && <PromptDeleteDialog key={`delete-${deletingPrompt.id}`} isOpen={true} onClose={() => setDeletingPrompt(null)} onConfirm={handleDeleteConfirm} promptName={deletingPrompt.name} />}
            </>
        );
    }

    // Main prompts view
    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Prompts"
                buttons={[
                    <Button key="importPrompt" variant="ghost" title="Import Prompt" onClick={() => setShowImportDialog(true)}>
                        <Download className="size-4" />
                        Import Prompt
                    </Button>,
                    <Button key="refreshPrompts" data-testid="refreshPrompts" disabled={isLoading} variant="ghost" title="Refresh Prompts" onClick={() => fetchPromptGroups()}>
                        <RefreshCcw className="size-4" />
                        Refresh Prompts
                    </Button>,
                ]}
            />

            {isLoading ? (
                <EmptyState title="Loading prompts..." variant="loading" />
            ) : (
                <div className="relative flex-1 p-4">
                    <PromptCards
                        prompts={promptGroups}
                        onManualCreate={() => navigate("/prompts/new?mode=manual")}
                        onAIAssisted={() => setShowGenerateDialog(true)}
                        onEdit={handleEdit}
                        onDelete={handleDeleteClick}
                        onViewVersions={group => navigate(`/prompts/${group.id}/versions`)}
                        onUseInChat={handleUseInChat}
                        onTogglePin={handleTogglePin}
                        onExport={handleExport}
                        newlyCreatedPromptId={newlyCreatedPromptId}
                    />
                </div>
            )}

            {/* Delete Confirmation Dialog */}
            {deletingPrompt && <PromptDeleteDialog key={`delete-${deletingPrompt.id}`} isOpen={true} onClose={() => setDeletingPrompt(null)} onConfirm={handleDeleteConfirm} promptName={deletingPrompt.name} />}

            {/* Generate Prompt Dialog */}
            <GeneratePromptDialog isOpen={showGenerateDialog} onClose={() => setShowGenerateDialog(false)} onGenerate={handleGeneratePrompt} />

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

            {/* Import Dialog */}
            <PromptImportDialog open={showImportDialog} onOpenChange={setShowImportDialog} onImport={handleImport} />
        </div>
    );
};
