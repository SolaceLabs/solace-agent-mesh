import React, { useState, useEffect, useMemo } from 'react';
import {
    Button,
    Input,
    Textarea,
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
    Label,
    CardTitle,
} from '@/lib/components/ui';
import { Sparkles, Loader2, AlertCircle, Pencil } from 'lucide-react';
import { Header } from '@/lib/components/header';
import { MessageBanner } from '@/lib/components/common';
import { usePromptTemplateBuilder } from './hooks/usePromptTemplateBuilder';
import { useUnsavedChangesWarning } from '@/lib/hooks';
import { useUnsavedChangesContext } from '@/lib/contexts';
import { PromptBuilderChat } from './PromptBuilderChat';
import { TemplatePreviewPanel } from './TemplatePreviewPanel';
import type { PromptGroup } from '@/lib/types/prompts';

interface PromptTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: (createdNewVersion?: boolean, createdPromptId?: string | null) => void;
    initialMessage?: string | null;
    editingGroup?: PromptGroup | null;
    isEditing?: boolean;
    initialMode?: 'manual' | 'ai-assisted';
}

export const PromptTemplateBuilder: React.FC<PromptTemplateBuilderProps> = ({
    onBack,
    onSuccess,
    initialMessage,
    editingGroup,
    isEditing = false,
    initialMode,
}) => {
    const {
        config,
        updateConfig,
        saveTemplate,
        updateTemplate,
        resetConfig,
        validationErrors,
        isLoading,
    } = usePromptTemplateBuilder(editingGroup);

    const [builderMode, setBuilderMode] = useState<'manual' | 'ai-assisted'>(
        initialMode || (isEditing ? 'manual' : 'ai-assisted')
    );
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);
    
    // Track initial config for unsaved changes detection
    const [initialConfig, setInitialConfig] = useState<typeof config | null>(null);
    
    // Global unsaved changes context
    const { setHasUnsavedChanges: setGlobalUnsavedChanges, checkUnsavedChanges } = useUnsavedChangesContext();

    // Pre-populate config when editing and capture initial state
    useEffect(() => {
        if (editingGroup && isEditing) {
            const initialData = {
                name: editingGroup.name,
                description: editingGroup.description,
                category: editingGroup.category,
                command: editingGroup.command,
                prompt_text: editingGroup.production_prompt?.prompt_text || '',
            };
            updateConfig(initialData);
            setInitialConfig(initialData);
        } else {
            // For new prompts, set empty initial config
            setInitialConfig({
                name: '',
                description: '',
                category: undefined,
                command: '',
                prompt_text: '',
            });
        }
    }, [editingGroup, isEditing, updateConfig]);
    
    // Check if there are unsaved changes
    const hasUnsavedChanges = useMemo(() => {
        if (!initialConfig) return false;
        
        // Check if current form has any actual content
        const hasContent = !!(
            config.name?.trim() ||
            config.description?.trim() ||
            config.category ||
            config.command?.trim() ||
            config.prompt_text?.trim()
        );
        
        // If form is empty, no unsaved changes
        if (!hasContent) return false;
        
        // Otherwise, check if values differ from initial state
        return (
            config.name !== initialConfig.name ||
            config.description !== initialConfig.description ||
            config.category !== initialConfig.category ||
            config.command !== initialConfig.command ||
            config.prompt_text !== initialConfig.prompt_text
        );
    }, [config, initialConfig]);
    
    // Update global unsaved changes state
    useEffect(() => {
        setGlobalUnsavedChanges(hasUnsavedChanges);
        return () => {
            // Clean up when component unmounts
            setGlobalUnsavedChanges(false);
        };
    }, [hasUnsavedChanges, setGlobalUnsavedChanges]);
    
    // Unsaved changes warning
    const { ConfirmNavigationDialog, confirmNavigation } = useUnsavedChangesWarning({
        hasUnsavedChanges,
    });

    const handleClose = (skipCheck = false) => {
        const doClose = () => {
            resetConfig();
            setBuilderMode('ai-assisted');
            setIsReadyToSave(false);
            setHighlightedFields([]);
            setInitialConfig(null);
            onBack();
        };

        if (hasUnsavedChanges && !skipCheck) {
            // Use global context to show styled dialog
            checkUnsavedChanges(doClose);
        } else {
            doClose();
        }
    };

    // Check if there are any validation errors
    const hasValidationErrors = Object.keys(validationErrors).length > 0;
    const validationErrorMessages = Object.values(validationErrors).filter(Boolean);

    const handleSave = async () => {
        if (isEditing && editingGroup) {
            // Overwrite current version
            const success = await updateTemplate(editingGroup.id, false);
            if (success) {
                // Clear unsaved state and close without check
                setGlobalUnsavedChanges(false);
                confirmNavigation();
                handleClose(true); // Skip unsaved check
                if (onSuccess) {
                    onSuccess(false, editingGroup.id); // Did not create new version, pass existing ID
                }
            }
        } else {
            const createdId = await saveTemplate();
            if (createdId) {
                // Clear unsaved state and close without check
                setGlobalUnsavedChanges(false);
                confirmNavigation();
                handleClose(true); // Skip unsaved check
                if (onSuccess) {
                    onSuccess(false, createdId); // New prompt, pass created ID
                }
            }
        }
    };

    const handleSaveNewVersion = async () => {
        if (!isEditing || !editingGroup) return;
        
        // Create new version and make it active
        const success = await updateTemplate(editingGroup.id, true);
        if (success) {
            // Clear unsaved state and close without check
            setGlobalUnsavedChanges(false);
            confirmNavigation();
            handleClose(true); // Skip unsaved check
            if (onSuccess) {
                onSuccess(true, editingGroup.id); // Created new version, pass group ID
            }
        }
    };

    const handleConfigUpdate = (updates: Record<string, unknown>) => {
        console.log('PromptTemplateBuilder: Received config updates:', updates);
        
        // Filter to only fields that actually changed
        const changedFields = Object.keys(updates).filter(key => {
            const oldValue = (config as Record<string, unknown>)[key];
            const newValue = updates[key];
            
            // Compare values, treating undefined/null/empty string as equivalent
            const normalizedOld = oldValue === undefined || oldValue === null || oldValue === '' ? '' : oldValue;
            const normalizedNew = newValue === undefined || newValue === null || newValue === '' ? '' : newValue;
            
            return normalizedOld !== normalizedNew;
        });
        
        console.log('PromptTemplateBuilder: Changed fields:', changedFields);
        
        updateConfig(updates);
        console.log('PromptTemplateBuilder: Config after update:', config);
        
        // Only show badges for fields that actually changed
        setHighlightedFields(changedFields);
    };

    const handleSwitchToManual = () => {
        setBuilderMode('manual');
        // Clear highlighted fields when switching to manual mode
        setHighlightedFields([]);
    };

    const handleSwitchToAI = () => {
        setBuilderMode('ai-assisted');
        // Clear highlighted fields when switching back to AI mode
        // This ensures "Updated" badges only show after new AI interactions
        setHighlightedFields([]);
    };

    return (
        <>
            {/* Unsaved Changes Dialog */}
            <ConfirmNavigationDialog />
            
            <div className="flex h-full flex-col">
            {/* Header with breadcrumbs */}
            <Header
                title={isEditing ? "Edit Prompt" : "Create Prompt"}
                breadcrumbs={[
                    { label: "Prompts", onClick: () => handleClose() },
                    { label: isEditing ? "Edit Prompt" : "Create Prompt" }
                ]}
                buttons={
                    builderMode === 'ai-assisted' ? [
                        <Button
                            key="edit-manually"
                            onClick={handleSwitchToManual}
                            variant="ghost"
                            size="sm"
                        >
                            <Pencil className="h-3 w-3 mr-1" />
                            Edit Manually
                        </Button>
                    ] : [
                        <Button
                            key="build-with-ai"
                            onClick={handleSwitchToAI}
                            variant="ghost"
                            size="sm"
                        >
                            <Sparkles className="h-3 w-3 mr-1" />
                            {isEditing ? 'Edit with AI' : 'Build with AI'}
                        </Button>
                    ]
                }
            />

            {/* Error Banner */}
            {hasValidationErrors && (
                <div className="px-8 py-3">
                    <MessageBanner
                        variant="error"
                        message={`Please fix the following errors: ${validationErrorMessages.join(', ')}`}
                    />
                </div>
            )}

            {/* Content area with left and right panels */}
            <div className="flex flex-1 min-h-0">
                {/* Left Panel - AI Chat (keep mounted but hidden to preserve chat history) */}
                <div className={`w-[40%] overflow-hidden border-r ${builderMode === 'manual' ? 'hidden' : ''}`}>
                    <PromptBuilderChat
                        onConfigUpdate={handleConfigUpdate}
                        currentConfig={config}
                        onReadyToSave={setIsReadyToSave}
                        initialMessage={initialMessage}
                    />
                </div>
                
                {/* Right Panel - Template Preview (only in AI mode) */}
                {builderMode === 'ai-assisted' && (
                    <div className="w-[60%] overflow-hidden bg-muted/30">
                        <TemplatePreviewPanel
                            config={config}
                            highlightedFields={highlightedFields}
                            isReadyToSave={isReadyToSave}
                        />
                    </div>
                )}
                
                {/* Manual Mode - Full Width Form */}
                {builderMode === 'manual' && (
                    <div className="flex-1 overflow-y-auto px-8 py-6">
                        <div className="max-w-4xl mx-auto space-y-6">
                        {/* Basic Information Section */}
                        <div>
                            <CardTitle className="text-base mb-4">Basic Information</CardTitle>
                            <div className="space-y-6">
                                {/* Template Name */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-name">Name <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <Input
                                        id="template-name"
                                        placeholder="e.g., Code Review Template"
                                        value={config.name || ''}
                                        onChange={(e) => updateConfig({ name: e.target.value })}
                                        className={`placeholder:text-muted-foreground/50 ${validationErrors.name ? 'border-red-500' : ''}`}
                                    />
                                    {validationErrors.name && (
                                        <p className="text-sm text-red-600 flex items-center gap-1">
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
                                        value={config.description || ''}
                                        onChange={(e) => updateConfig({ description: e.target.value })}
                                        className="placeholder:text-muted-foreground/50"
                                    />
                                </div>

                                {/* Tag */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-category">Tag</Label>
                                    <Select
                                        value={config.category || 'none'}
                                        onValueChange={(value) =>
                                            updateConfig({ category: value === 'none' ? undefined : value })
                                        }
                                    >
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
                                    <Label htmlFor="template-command">Chat Shortcut <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">/</span>
                                        <Input
                                            id="template-command"
                                            placeholder="e.g., code-review"
                                            value={config.command || ''}
                                            onChange={(e) => updateConfig({ command: e.target.value })}
                                            className={`placeholder:text-muted-foreground/50 ${validationErrors.command ? 'border-red-500' : ''}`}
                                        />
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Quick access shortcut for chat (letters, numbers, hyphens, underscores only)
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Content Section */}
                        <div>
                            <CardTitle className="text-base mb-4">Content<span className="text-[var(--color-primary-wMain)]">*</span></CardTitle>
                            <div className="space-y-2">
                                <Textarea
                                    id="template-prompt"
                                    data-testid="prompt-text-input"
                                    placeholder="Enter your prompt template here. Use {{Variable Name}} for placeholders."
                                    value={config.prompt_text || ''}
                                    onChange={(e) => updateConfig({ prompt_text: e.target.value })}
                                    rows={12}
                                    className={`font-mono placeholder:text-muted-foreground/50 ${validationErrors.prompt_text ? 'border-red-500' : ''}`}
                                />
                                {validationErrors.prompt_text && (
                                    <p className="text-sm text-red-600 flex items-center gap-1">
                                        <AlertCircle className="h-3 w-3" />
                                        {validationErrors.prompt_text}
                                    </p>
                                )}
                                
                                {/* Variables info - always shown */}
                                <div className="space-y-2">
                                    <p className="text-sm text-muted-foreground">
                                        Variables are placeholder values that make your prompt flexible and reusable. You will be asked to fill in these variable values whenever you use this prompt. Use {`{{Variable Name}}`} for placeholders.
                                        {config.detected_variables && config.detected_variables.length > 0 && ' Your prompt has the following variables:'}
                                    </p>
                                    {config.detected_variables && config.detected_variables.length > 0 && (
                                        <div className="flex flex-wrap gap-2">
                                            {config.detected_variables.map((variable, index) => (
                                                <span
                                                    key={index}
                                                    className="px-2 py-1 bg-primary/10 text-primary text-xs font-mono rounded"
                                                >
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

            {/* Footer Actions */}
            <div className="flex justify-end gap-2 p-4 border-t">
                <Button variant="ghost" onClick={() => handleClose()} disabled={isLoading}>
                    {isEditing ? 'Discard Changes' : 'Cancel'}
                </Button>
                {isEditing && (
                    <Button
                        variant="outline"
                        onClick={handleSaveNewVersion}
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            'Save New Version'
                        )}
                    </Button>
                )}
                <Button
                    onClick={handleSave}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            {isEditing ? 'Saving...' : 'Creating...'}
                        </>
                    ) : (
                        isEditing ? 'Save' : 'Create'
                    )}
                </Button>
            </div>
        </div>
        </>
    );
};