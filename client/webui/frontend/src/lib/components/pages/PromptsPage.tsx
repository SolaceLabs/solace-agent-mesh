import { useState, useEffect, useCallback } from "react";
import { useLoaderData, useNavigate, useLocation } from "react-router-dom";
import { RefreshCcw, Upload } from "lucide-react";

import type { PromptGroup } from "@/lib/types/prompts";
import type { PromptImportData } from "@/lib/schemas";
import { Button, EmptyState, Header, VariableDialog } from "@/lib/components";
import { GeneratePromptDialog, PromptCards, PromptDeleteDialog, PromptTemplateBuilder, VersionHistoryPage, PromptImportDialog } from "@/lib/components/prompts";
import { detectVariables, downloadBlob, getErrorMessage } from "@/lib/utils";
import { api } from "@/lib/api";
import { useChatContext } from "@/lib/hooks";

/**
 * Main page for managing prompt library with AI-assisted builder
 */
export const PromptsPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const loaderData = useLoaderData<{ promptId?: string; view?: string; mode?: string }>();

    const { addNotification, displayError } = useChatContext();
    const [promptGroups, setPromptGroups] = useState<PromptGroup[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [showBuilder, setShowBuilder] = useState(false);
    const [showGenerateDialog, setShowGenerateDialog] = useState(false);
    const [initialMessage, setInitialMessage] = useState<string | null>(null);
    const [editingGroup, setEditingGroup] = useState<PromptGroup | null>(null);
    const [builderInitialMode, setBuilderInitialMode] = useState<"manual" | "ai-assisted">("ai-assisted");
    const [builderKey, setBuilderKey] = useState(0); // Key to force fresh PromptTemplateBuilder instance
    const [versionHistoryGroup, setVersionHistoryGroup] = useState<PromptGroup | null>(null);
    const [deletingPrompt, setDeletingPrompt] = useState<{ id: string; name: string } | null>(null);
    const [newlyCreatedPromptId, setNewlyCreatedPromptId] = useState<string | null>(null);
    const [showVariableDialog, setShowVariableDialog] = useState(false);
    const [pendingPromptGroup, setPendingPromptGroup] = useState<PromptGroup | null>(null);
    const [showImportDialog, setShowImportDialog] = useState(false);

    const fetchPromptGroups = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await api.webui.get("/api/v1/prompts/groups/all");
            setPromptGroups(data);
        } catch (error) {
            displayError({ title: "Failed to Load Prompts", error: getErrorMessage(error, "An error occurred while fetching prompt groups.") });
        } finally {
            setIsLoading(false);
        }
    }, [displayError]);

    useEffect(() => {
        fetchPromptGroups();
    }, [fetchPromptGroups]);

    // Handle route-based views from loaderData
    useEffect(() => {
        if (loaderData?.view === "builder") {
            // Show builder based on mode
            if (loaderData.mode === "edit" && loaderData.promptId) {
                // Load the prompt group for editing
                const loadPromptForEdit = async () => {
                    try {
                        const data = await api.webui.get(`/api/v1/prompts/groups/${loaderData.promptId}`);
                        setEditingGroup(data);
                        setBuilderInitialMode("ai-assisted"); // Always start in AI-assisted mode for editing
                        setShowBuilder(true);
                    } catch (error) {
                        displayError({ title: "Failed to Edit Prompt", error: getErrorMessage(error, "An error occurred while fetching prompt.") });
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
                } else {
                    // Clear any previous initial message when starting fresh
                    setInitialMessage(null);
                }

                // Increment key to force fresh PromptTemplateBuilder instance
                setBuilderKey(prev => prev + 1);
                setShowBuilder(true);
            }
        } else if (loaderData?.view === "versions" && loaderData.promptId) {
            // Load the prompt group for version history
            const loadPromptGroup = async () => {
                try {
                    const data = await api.webui.get(`/api/v1/prompts/groups/${loaderData.promptId}`);
                    setVersionHistoryGroup(data);
                } catch (error) {
                    displayError({ title: "Failed to View Versions", error: getErrorMessage(error, "An error occurred while fetching versions.") });
                }
            };
            loadPromptGroup();
        } else {
            // Main list view - reset states
            setShowBuilder(false);
            setVersionHistoryGroup(null);
            setEditingGroup(null);
        }
    }, [loaderData, location.state?.taskDescription, displayError]);

    const handleDeleteClick = (id: string, name: string) => {
        setDeletingPrompt({ id, name });
    };

    const handleDeleteConfirm = async () => {
        if (!deletingPrompt) return;

        try {
            await api.webui.delete(`/api/v1/prompts/groups/${deletingPrompt.id}`);
            if (versionHistoryGroup?.id === deletingPrompt.id) {
                setVersionHistoryGroup(null);
            }
            await fetchPromptGroups();
            setDeletingPrompt(null);
            addNotification("Prompt deleted", "success");
        } catch (error) {
            setDeletingPrompt(null);
            displayError({ title: "Failed to Delete Prompt", error: getErrorMessage(error, "An error occurred while deleting the prompt.") });
        }
    };

    const handleEdit = (group: PromptGroup) => {
        navigate(`/prompts/${group.id}/edit`);
    };

    const handleRestoreVersion = async (promptId: string) => {
        try {
            await api.webui.patch(`/api/v1/prompts/${promptId}/make-production`);
            fetchPromptGroups();
            addNotification("Version made active", "success");
        } catch (error) {
            displayError({ title: "Failed to Update Version", error: getErrorMessage(error, "An error occurred while making the version active.") });
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
        const promptText = prompt.productionPrompt?.promptText || "";

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
            setPromptGroups(prev => prev.map(p => (p.id === id ? { ...p, isPinned: !currentStatus } : p)));

            await api.webui.patch(`/api/v1/prompts/groups/${id}/pin`);
        } catch (error) {
            // Revert on error
            setPromptGroups(prev => prev.map(p => (p.id === id ? { ...p, isPinned: currentStatus } : p)));
            displayError({ title: "Failed to Update Pin Status", error: getErrorMessage(error, "An error occurred while updating the pin status.") });
        }
    };

    const handleExport = async (prompt: PromptGroup) => {
        try {
            const data = await api.webui.get(`/api/v1/prompts/groups/${prompt.id}/export`);

            // Create a blob and trigger download using utility
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const filename = `prompt-${prompt.name.replace(/[^a-z0-9]/gi, "-").toLowerCase()}-${Date.now()}.json`;
            downloadBlob(blob, filename);

            addNotification("Prompt exported successfully", "success");
        } catch (error) {
            displayError({ title: "Failed to Export Prompt", error: getErrorMessage(error, "An error occurred while exporting the prompt.") });
        }
    };

    const handleImport = async (importData: PromptImportData, options: { preserveCommand: boolean; preserveCategory: boolean }) => {
        try {
            // Convert camelCase to snake_case for backend API
            const apiPayload = {
                prompt_data: {
                    version: importData.version,
                    exported_at: importData.exportedAt,
                    prompt: {
                        name: importData.prompt.name,
                        description: importData.prompt.description,
                        category: importData.prompt.category,
                        command: importData.prompt.command,
                        prompt_text: importData.prompt.promptText,
                        metadata: importData.prompt.metadata
                            ? {
                                  author_name: importData.prompt.metadata.authorName,
                                  original_version: importData.prompt.metadata.originalVersion,
                                  original_created_at: importData.prompt.metadata.originalCreatedAt,
                              }
                            : undefined,
                    },
                },
                options: {
                    preserve_command: options.preserveCommand,
                    preserve_category: options.preserveCategory,
                },
            };

            const result = await api.webui.post("/api/v1/prompts/import", apiPayload);

            // Navigate back to prompts page
            setShowBuilder(false);
            setShowImportDialog(false);
            setInitialMessage(null);
            setEditingGroup(null);

            // Refresh prompts and select the newly imported one
            await fetchPromptGroups();
            setNewlyCreatedPromptId(result.prompt_group_id);

            // Filter out truncation warnings since user was already informed in the dialog
            // Only show non-truncation warnings (e.g., command conflicts)
            const nonTruncationWarnings = (result.warnings || []).filter((warning: string) => !warning.toLowerCase().includes("truncated"));

            // Show notification - include non-truncation warnings if any
            if (nonTruncationWarnings.length > 0) {
                const warningText = nonTruncationWarnings.length === 1 ? nonTruncationWarnings[0] : nonTruncationWarnings.join("; ");
                addNotification(`Prompt imported with notes: ${warningText}`, "info");
            } else {
                addNotification("Prompt imported", "success");
            }
        } catch (error) {
            console.error("Failed to import prompt:", error);
            throw error; // Re-throw to let dialog handle it
        }
    };

    if (showBuilder) {
        return (
            <>
                <PromptTemplateBuilder
                    key={`builder-${builderKey}-${editingGroup?.id || "new"}`}
                    onBack={() => {
                        navigate("/prompts");
                    }}
                    onSuccess={async (createdPromptId?: string | null) => {
                        // Store the newly created/edited prompt ID for auto-selection
                        if (createdPromptId) {
                            setNewlyCreatedPromptId(createdPromptId);
                        }

                        await fetchPromptGroups();
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
                        <Upload className="size-4" />
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
                <div className="bg-card-background relative flex-1 p-4">
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

            {deletingPrompt && <PromptDeleteDialog key={`delete-${deletingPrompt.id}`} isOpen={true} onClose={() => setDeletingPrompt(null)} onConfirm={handleDeleteConfirm} promptName={deletingPrompt.name} />}

            <GeneratePromptDialog isOpen={showGenerateDialog} onClose={() => setShowGenerateDialog(false)} onGenerate={handleGeneratePrompt} />

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

            <PromptImportDialog open={showImportDialog} onOpenChange={setShowImportDialog} onImport={handleImport} existingPrompts={promptGroups} />
        </div>
    );
};
