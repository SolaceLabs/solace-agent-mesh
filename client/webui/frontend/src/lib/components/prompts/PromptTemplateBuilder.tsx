import React, { useState, useEffect } from 'react';
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
import { usePromptTemplateBuilder } from './hooks/usePromptTemplateBuilder';
import { PromptBuilderChat } from './PromptBuilderChat';
import { TemplatePreviewPanel } from './TemplatePreviewPanel';
import type { PromptGroup } from '@/lib/types/prompts';
import { MessageBanner } from '@/lib/components/common';

interface PromptTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: () => void;
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
    const [showNoChangeWarning, setShowNoChangeWarning] = useState(false);

    // Pre-populate config when editing
    useEffect(() => {
        if (editingGroup && isEditing) {
            updateConfig({
                name: editingGroup.name,
                description: editingGroup.description,
                category: editingGroup.category,
                command: editingGroup.command,
                prompt_text: editingGroup.production_prompt?.prompt_text || '',
            });
        }
    }, [editingGroup, isEditing]);

    const handleClose = () => {
        resetConfig();
        setBuilderMode('ai-assisted');
        setIsReadyToSave(false);
        setHighlightedFields([]);
        onBack();
    };

    // Check if there are any validation errors
    const hasValidationErrors = Object.keys(validationErrors).length > 0;
    const validationErrorMessages = Object.values(validationErrors).filter(Boolean);

    const handleSave = async () => {
        if (isEditing && editingGroup) {
            const success = await updateTemplate(editingGroup.id, false);
            if (success) {
                handleClose();
                if (onSuccess) {
                    onSuccess();
                }
            }
        } else {
            const success = await saveTemplate();
            if (success) {
                handleClose();
                if (onSuccess) {
                    onSuccess();
                }
            }
        }
    };

    const handleSaveNewVersion = async () => {
        if (!isEditing || !editingGroup) return;
        
        // Check if prompt text has changed
        if (config.prompt_text === editingGroup.production_prompt?.prompt_text) {
            setShowNoChangeWarning(true);
            setTimeout(() => setShowNoChangeWarning(false), 5000);
            return;
        }
        
        const success = await updateTemplate(editingGroup.id, true);
        if (success) {
            handleClose();
            if (onSuccess) {
                onSuccess();
            }
        }
    };

    const handleConfigUpdate = (updates: Record<string, any>) => {
        console.log('PromptTemplateBuilder: Received config updates:', updates);
        updateConfig(updates);
        console.log('PromptTemplateBuilder: Config after update:', config);
        const updatedFields = Object.keys(updates);
        setHighlightedFields(updatedFields);
        setTimeout(() => {
            setHighlightedFields([]);
        }, 6000); // 6 seconds
    };

    const handleSwitchToManual = () => {
        setBuilderMode('manual');
    };

    const handleSwitchToAI = () => {
        setBuilderMode('ai-assisted');
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header with breadcrumbs */}
            <Header
                title={isEditing ? "Edit Prompt Template" : "Create Prompt Template"}
                breadcrumbs={[
                    { label: "Prompts", onClick: handleClose },
                    { label: isEditing ? "Edit Prompt Template" : "Create Prompt Template" }
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

            {/* Warning Banner */}
            {showNoChangeWarning && (
                <MessageBanner
                    variant="warning"
                    message="No changes detected in prompt text. Please modify the prompt text to create a new version."
                />
            )}

            {/* Error Banner */}
            {hasValidationErrors && (
                <div className="bg-destructive/10 border-b border-destructive/20 px-8 py-3">
                    <div className="flex items-start gap-2">
                        <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <p className="text-sm font-medium text-destructive mb-1">Please fix the following errors:</p>
                            <ul className="text-sm text-destructive/90 list-disc list-inside space-y-0.5">
                                {validationErrorMessages.map((error, index) => (
                                    <li key={index}>{error}</li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>
            )}

            {/* Content area with left and right panels */}
            <div className="flex flex-1 min-h-0">
                {builderMode === 'ai-assisted' ? (
                    <>
                        {/* Left Panel - AI Chat */}
                        <div className="w-[40%] overflow-hidden border-r">
                            <PromptBuilderChat
                                onConfigUpdate={handleConfigUpdate}
                                currentConfig={config}
                                onReadyToSave={setIsReadyToSave}
                                initialMessage={initialMessage}
                            />
                        </div>
                        {/* Right Panel - Template Preview */}
                        <div className="w-[60%] overflow-hidden bg-muted/30">
                            <TemplatePreviewPanel
                                config={config}
                                highlightedFields={highlightedFields}
                                isReadyToSave={isReadyToSave}
                            />
                        </div>
                    </>
                ) : (
                    /* Manual Mode - Full Width Form */
                    <div className="flex-1 overflow-y-auto px-8 py-6">
                        <div className="max-w-4xl mx-auto space-y-6">
                        {/* Basic Information Section */}
                        <div>
                            <CardTitle className="text-base mb-4">Basic Information</CardTitle>
                            <div className="space-y-6">
                                {/* Template Name */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-name">Template Name <span className="text-[var(--color-primary-wMain)]">*</span></Label>
                                    <Input
                                        id="template-name"
                                        placeholder="e.g., Code Review Template"
                                        value={config.name || ''}
                                        onChange={(e) => updateConfig({ name: e.target.value })}
                                        className={validationErrors.name ? 'border-red-500' : ''}
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
                                        placeholder="Brief description of what this template does"
                                        value={config.description || ''}
                                        onChange={(e) => updateConfig({ description: e.target.value })}
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
                                    <Label htmlFor="template-command">Chat Shortcut (Optional)</Label>
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-muted-foreground">/</span>
                                        <Input
                                            id="template-command"
                                            placeholder="code-review"
                                            value={config.command || ''}
                                            onChange={(e) => updateConfig({ command: e.target.value })}
                                            className={validationErrors.command ? 'border-red-500' : ''}
                                        />
                                    </div>
                                    {validationErrors.command && (
                                        <p className="text-sm text-red-600 flex items-center gap-1">
                                            <AlertCircle className="h-3 w-3" />
                                            {validationErrors.command}
                                        </p>
                                    )}
                                    <p className="text-xs text-muted-foreground">
                                        Quick access shortcut for chat (letters, numbers, hyphens, underscores only)
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Prompt Template Section */}
                        <div>
                            <CardTitle className="text-base mb-4">Prompt Template<span className="text-[var(--color-primary-wMain)]">*</span></CardTitle>
                            <div className="space-y-2">
                                <div className="relative">
                                    <Textarea
                                        id="template-prompt"
                                        placeholder="Enter your prompt template here. Use {{variable_name}} for placeholders."
                                        value={config.prompt_text || ''}
                                        onChange={(e) => updateConfig({ prompt_text: e.target.value })}
                                        rows={12}
                                        className={`font-mono ${validationErrors.prompt_text ? 'border-red-500' : ''}`}
                                        style={{
                                            color: config.prompt_text ? 'transparent' : undefined,
                                            caretColor: 'var(--foreground)'
                                        }}
                                    />
                                    {config.prompt_text && (
                                        <div
                                            className="absolute inset-0 pointer-events-none px-3 py-2 text-sm font-mono whitespace-pre-wrap overflow-hidden"
                                            style={{ lineHeight: '1.5' }}
                                        >
                                            {config.prompt_text.split(/(\{\{[^}]+\}\})/g).map((part, index) => {
                                                if (part.match(/\{\{[^}]+\}\}/)) {
                                                    return (
                                                        <span key={index} className="bg-primary/20 text-primary font-medium px-1 rounded">
                                                            {part}
                                                        </span>
                                                    );
                                                }
                                                return <span key={index} className="text-foreground">{part}</span>;
                                            })}
                                        </div>
                                    )}
                                </div>
                                {validationErrors.prompt_text && (
                                    <p className="text-sm text-red-600 flex items-center gap-1">
                                        <AlertCircle className="h-3 w-3" />
                                        {validationErrors.prompt_text}
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Use double curly braces for variables: {`{{variable_name}}`}
                                </p>
                            </div>
                        </div>

                        {/* Variables Section */}
                        {config.detected_variables && config.detected_variables.length > 0 && (
                            <div>
                                <CardTitle className="text-base mb-4">Variables</CardTitle>
                                <div className="space-y-3">
                                    <p className="text-sm text-muted-foreground leading-relaxed">
                                        Variables are placeholder values that make your prompt flexible and reusable. Variables are enclosed in double brackets like <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{'{{VARIABLE_NAME}}'}</code>. You will be asked to fill in these variable values whenever you use this prompt. The prompt above has the following variables:
                                    </p>
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
                                </div>
                            </div>
                        )}
                        </div>
                    </div>
                )}
            </div>

            {/* Footer Actions */}
            <div className="flex justify-end gap-2 p-4 border-t">
                <Button variant="ghost" onClick={handleClose} disabled={isLoading}>
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
    );
};