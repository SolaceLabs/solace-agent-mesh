import React, { useState, useEffect } from "react";
import { Sparkles, Loader2, AlertCircle, Pencil } from "lucide-react";

import { Button, Input, HighlightedTextarea, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Label, CardTitle } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { MessageBanner } from "@/lib/components/common";
import { useNavigationBlocker } from "@/lib/hooks";
import type { PromptGroup } from "@/lib/types/prompts";

import { usePromptTemplateBuilder } from "./hooks/usePromptTemplateBuilder";
import { PromptBuilderChat } from "./PromptBuilderChat";
import { TemplatePreviewPanel } from "./TemplatePreviewPanel";

interface PromptTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: (createdPromptId?: string | null) => void;
    initialMessage?: string | null;
    editingGroup?: PromptGroup | null;
    isEditing?: boolean;
    initialMode?: "manual" | "ai-assisted";
}

export const PromptTemplateBuilder: React.FC<PromptTemplateBuilderProps> = ({ onBack, onSuccess, initialMessage, editingGroup, isEditing = false, initialMode }) => {
    const { config, updateConfig, saveTemplate, updateTemplate, resetConfig, validationErrors, isLoading } = usePromptTemplateBuilder(editingGroup);

    const [builderMode, setBuilderMode] = useState<"manual" | "ai-assisted">(initialMode || "ai-assisted");
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);

    // For unsaved changes detection
    const [initialConfig, setInitialConfig] = useState<typeof config | null>(null);
    const { allowNavigation, NavigationBlocker, setBlockingEnabled } = useNavigationBlocker();

    // Pre-populate config when editing and capture initial state
    useEffect(() => {
        if (editingGroup && isEditing) {
            const initialData = {
                name: editingGroup.name,
                description: editingGroup.description,
                category: editingGroup.category,
                command: editingGroup.command,
                promptText: editingGroup.productionPrompt?.promptText || "",
            };
            updateConfig(initialData);
            setInitialConfig(initialData);
        } else {
            // For new prompts, set empty initial config
            setInitialConfig({
                name: "",
                description: "",
                category: undefined,
                command: "",
                promptText: "",
            });
        }
    }, [editingGroup, isEditing, updateConfig]);

    // Enable/disable navigation blocking based on unsaved changes
    useEffect(() => {
        if (!initialConfig) {
            setBlockingEnabled(false);
            return;
        }

        // Check if current form has any actual content
        const hasContent = !!(config.name?.trim() || config.description?.trim() || config.category || config.command?.trim() || config.promptText?.trim());

        // If form is empty, no unsaved changes
        if (!hasContent) {
            setBlockingEnabled(false);
            return;
        }

        // Otherwise, check if values differ from initial state
        const hasUnsavedChanges =
            config.name !== initialConfig.name || config.description !== initialConfig.description || config.category !== initialConfig.category || config.command !== initialConfig.command || config.promptText !== initialConfig.promptText;

        setBlockingEnabled(hasUnsavedChanges);
    }, [config, initialConfig, setBlockingEnabled]);

    const handleClose = (skipCheck = false) => {
        if (skipCheck) {
            allowNavigation(() => {
                resetConfig();
                setBuilderMode("ai-assisted");
                setIsReadyToSave(false);
                setHighlightedFields([]);
                setInitialConfig(null);
                onBack();
            });
        } else {
            onBack();
        }
    };

    // Check if there are any validation errors
    const hasValidationErrors = Object.keys(validationErrors).length > 0;
    const validationErrorMessages = Object.values(validationErrors).filter(Boolean);

    const handleSave = async () => {
        if (isEditing && editingGroup) {
            const success = await updateTemplate(editingGroup.id, false);
            if (success) {
                allowNavigation(() => {
                    handleClose(true);
                    if (onSuccess) {
                        onSuccess(editingGroup.id);
                    }
                });
            }
        } else {
            const createdId = await saveTemplate();
            if (createdId) {
                allowNavigation(() => {
                    handleClose(true);
                    if (onSuccess) {
                        onSuccess(createdId);
                    }
                });
            }
        }
    };

    const handleSaveNewVersion = async () => {
        if (!isEditing || !editingGroup) return;

        // Create new version and make it active
        const success = await updateTemplate(editingGroup.id, true);
        if (success) {
            // Clear unsaved state and close without check
            allowNavigation(() => {
                handleClose(true);
                if (onSuccess) {
                    onSuccess(editingGroup.id);
                }
            });
        }
    };

    const handleConfigUpdate = (updates: Record<string, unknown>) => {
        // Filter to only fields that actually changed
        const changedFields = Object.keys(updates).filter(key => {
            const oldValue = (config as Record<string, unknown>)[key];
            const newValue = updates[key];

            // Compare values, treating undefined/null/empty string as equivalent
            const normalizedOld = oldValue === undefined || oldValue === null || oldValue === "" ? "" : oldValue;
            const normalizedNew = newValue === undefined || newValue === null || newValue === "" ? "" : newValue;

            return normalizedOld !== normalizedNew;
        });

        updateConfig(updates);
        // Only show badges for fields that actually changed
        setHighlightedFields(changedFields);
    };

    const handleSwitchToManual = () => {
        setBuilderMode("manual");
        // Clear highlighted fields when switching to manual mode
        setHighlightedFields([]);
    };

    const handleSwitchToAI = () => {
        setBuilderMode("ai-assisted");
        // Clear highlighted fields when switching back to AI mode
        // This ensures "Updated" badges only show after new AI interactions
        setHighlightedFields([]);
    };

    return (
        <>
            <div className="flex h-full flex-col">
                {/* Header with breadcrumbs */}
                <Header
                    title={isEditing ? "Edit Prompt" : "Create Prompt"}
                    breadcrumbs={[{ label: "Prompts", onClick: () => handleClose() }, { label: isEditing ? "Edit Prompt" : "Create Prompt" }]}
                    buttons={
                        builderMode === "ai-assisted"
                            ? [
                                  <Button data-testid="editManuallyButton" key="edit-manually" onClick={handleSwitchToManual} variant="ghost" size="sm">
                                      <Pencil className="mr-1 h-3 w-3" />
                                      Edit Manually
                                  </Button>,
                              ]
                            : [
                                  <Button data-testid="buildWithAIButton" key="build-with-ai" onClick={handleSwitchToAI} variant="ghost" size="sm">
                                      <Sparkles className="mr-1 h-3 w-3" />
                                      {isEditing ? "Edit with AI" : "Build with AI"}
                                  </Button>,
                              ]
                    }
                />

                {/* Error Banner */}
                {hasValidationErrors && (
                    <div className="px-8 py-3">
                        <MessageBanner variant="error" message={`Please fix the following errors: ${validationErrorMessages.join(", ")}`} />
                    </div>
                )}

                {/* Content area with left and right panels */}
                <div className="flex min-h-0 flex-1">
                    {/* Left Panel - AI Chat (keep mounted but hidden to preserve chat history) */}
                    <div className={`w-[40%] overflow-hidden border-r ${builderMode === "manual" ? "hidden" : ""}`}>
                        <PromptBuilderChat onConfigUpdate={handleConfigUpdate} currentConfig={config} onReadyToSave={setIsReadyToSave} initialMessage={initialMessage} isEditing={isEditing} />
                    </div>

                    {/* Right Panel - Template Preview (only in AI mode) */}
                    {builderMode === "ai-assisted" && (
                        <div className="w-[60%] overflow-hidden">
                            <TemplatePreviewPanel config={config} highlightedFields={highlightedFields} isReadyToSave={isReadyToSave} />
                        </div>
                    )}

                    {/* Manual Mode - Full Width Form */}
                    {builderMode === "manual" && (
                        <div className="flex-1 overflow-y-auto px-8 py-6">
                            <div className="mx-auto max-w-4xl space-y-6">
                                {/* Basic Information Section */}
                                <div>
                                    <CardTitle className="mb-4 text-base">Basic Information</CardTitle>
                                    <div className="space-y-6">
                                        {/* Template Name */}
                                        <div className="space-y-2">
                                            <Label htmlFor="template-name">
                                                Name <span className="text-[var(--color-primary-wMain)]">*</span>
                                            </Label>
                                            <Input
                                                id="template-name"
                                                placeholder="e.g., Code Review Template"
                                                value={config.name || ""}
                                                onChange={e => updateConfig({ name: e.target.value })}
                                                className={`placeholder:text-muted-foreground/50 ${validationErrors.name ? "border-red-500" : ""}`}
                                            />
                                            {validationErrors.name && (
                                                <p className="flex items-center gap-1 text-sm text-red-600">
                                                    <AlertCircle className="h-3 w-3" />
                                                    {validationErrors.name}
                                                </p>
                                            )}
                                        </div>

                                        {/* Description */}
                                        <div className="space-y-2">
                                            <Label htmlFor="template-description">Description</Label>
                                            <Input
                                                id="template-description"
                                                placeholder="e.g., Reviews code for best practices and potential issues"
                                                value={config.description || ""}
                                                onChange={e => updateConfig({ description: e.target.value })}
                                                className="placeholder:text-muted-foreground/50"
                                            />
                                        </div>

                                        {/* Tag */}
                                        <div className="space-y-2">
                                            <Label htmlFor="template-category">Tag</Label>
                                            <Select value={config.category || "none"} onValueChange={value => updateConfig({ category: value === "none" ? undefined : value })}>
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select tag" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">No Tag</SelectItem>
                                                    <SelectItem value="Development">Development</SelectItem>
                                                    <SelectItem value="Analysis">Analysis</SelectItem>
                                                    <SelectItem value="Documentation">Documentation</SelectItem>
                                                    <SelectItem value="Communication">Communication</SelectItem>
                                                    <SelectItem value="Testing">Testing</SelectItem>
                                                    <SelectItem value="Other">Other</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        {/* Chat Shortcut */}
                                        <div className="space-y-2">
                                            <Label htmlFor="template-command">
                                                Chat Shortcut <span className="text-[var(--color-primary-wMain)]">*</span>
                                            </Label>
                                            <div className="flex items-center gap-2">
                                                <span className="text-muted-foreground text-sm">/</span>
                                                <Input
                                                    id="template-command"
                                                    placeholder="e.g., code-review"
                                                    value={config.command || ""}
                                                    onChange={e => updateConfig({ command: e.target.value })}
                                                    className={`placeholder:text-muted-foreground/50 ${validationErrors.command ? "border-red-500" : ""}`}
                                                />
                                            </div>
                                            <p className="text-muted-foreground text-xs">Quick access shortcut for chat (letters, numbers, hyphens, underscores only)</p>
                                        </div>
                                    </div>
                                </div>

                                {/* Content Section */}
                                <div>
                                    <CardTitle className="mb-4 text-base">
                                        Content<span className="text-[var(--color-primary-wMain)]">*</span>
                                    </CardTitle>
                                    <div className="space-y-2">
                                        <HighlightedTextarea
                                            id="template-prompt"
                                            data-testid="prompt-text-input"
                                            placeholder="Enter your prompt template here. Use {{Variable Name}} for placeholders."
                                            value={config.promptText || ""}
                                            onChange={e => updateConfig({ promptText: e.target.value })}
                                            rows={12}
                                            className={`placeholder:text-muted-foreground/50 ${validationErrors.promptText ? "border-red-500" : ""}`}
                                        />
                                        {validationErrors.promptText && (
                                            <p className="flex items-center gap-1 text-sm text-red-600">
                                                <AlertCircle className="h-3 w-3" />
                                                {validationErrors.promptText}
                                            </p>
                                        )}

                                        {/* Variables info - always shown */}
                                        <div className="space-y-2">
                                            <p className="text-muted-foreground text-sm">
                                                Variables are placeholder values that make your prompt flexible and reusable. You will be asked to fill in these variable values whenever you use this prompt. Use {`{{Variable Name}}`} for placeholders.
                                                {config.detected_variables && config.detected_variables.length > 0 && " Your prompt has the following variables:"}
                                            </p>
                                            {config.detected_variables && config.detected_variables.length > 0 && (
                                                <div className="flex flex-wrap gap-2">
                                                    {config.detected_variables.map((variable, index) => (
                                                        <span key={index} className="bg-primary/10 text-primary rounded px-2 py-1 font-mono text-xs">
                                                            {`{{${variable}}}`}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
                <NavigationBlocker />
                {/* Footer Actions */}
                <div className="flex justify-end gap-2 border-t p-4">
                    <Button variant="ghost" onClick={() => handleClose(isEditing)} disabled={isLoading}>
                        {isEditing ? "Discard Changes" : "Cancel"}
                    </Button>
                    {isEditing && (
                        <Button variant="outline" onClick={handleSaveNewVersion} disabled={isLoading}>
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                "Save New Version"
                            )}
                        </Button>
                    )}
                    <Button data-testid="createPromptButton" onClick={handleSave} disabled={isLoading}>
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                {isEditing ? "Saving..." : "Creating..."}
                            </>
                        ) : isEditing ? (
                            "Save"
                        ) : (
                            "Create"
                        )}
                    </Button>
                </div>
            </div>
        </>
    );
};
