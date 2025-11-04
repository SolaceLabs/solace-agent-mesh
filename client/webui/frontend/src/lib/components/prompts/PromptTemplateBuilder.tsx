import React, { useState } from 'react';
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
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/lib/components/ui';
import { Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { Header } from '@/lib/components/header';
import { usePromptTemplateBuilder } from './hooks/usePromptTemplateBuilder';
import { PromptBuilderChat } from './PromptBuilderChat';
import { TemplatePreviewPanel } from './TemplatePreviewPanel';

interface PromptTemplateBuilderProps {
    onBack: () => void;
    onSuccess?: () => void;
    initialMessage?: string | null;
}

export const PromptTemplateBuilder: React.FC<PromptTemplateBuilderProps> = ({
    onBack,
    onSuccess,
    initialMessage,
}) => {
    const {
        config,
        updateConfig,
        saveTemplate,
        resetConfig,
        validationErrors,
        isLoading,
    } = usePromptTemplateBuilder();

    const [builderMode, setBuilderMode] = useState<'manual' | 'ai-assisted'>('ai-assisted');
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);

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
        const success = await saveTemplate();
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

    const ModeSelector = () => (
        <div className="flex items-center gap-2 bg-muted rounded-lg p-1">
            <button
                onClick={() => setBuilderMode('manual')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    builderMode === 'manual'
                        ? 'bg-background shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                }`}
                disabled={isLoading}
            >
                Manual
            </button>
            <button
                onClick={() => setBuilderMode('ai-assisted')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-1.5 ${
                    builderMode === 'ai-assisted'
                        ? 'bg-background shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                }`}
                disabled={isLoading}
            >
                <Sparkles className="h-3.5 w-3.5" />
                AI-Assisted
            </button>
        </div>
    );

    return (
        <div className="flex h-full flex-col">
            {/* Header with breadcrumbs */}
            <Header
                title="Create Prompt Template"
                breadcrumbs={[
                    { label: "Prompts", onClick: handleClose },
                    { label: "Create Template" }
                ]}
                buttons={[
                    <div key="mode-selector">
                        <ModeSelector />
                    </div>
                ]}
            />

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
                                onEditManually={handleSwitchToManual}
                                highlightedFields={highlightedFields}
                                isReadyToSave={isReadyToSave}
                            />
                        </div>
                    </>
                ) : (
                    /* Manual Mode - Full Width Form */
                    <div className="flex-1 overflow-y-auto px-8 py-6">
                        <div className="max-w-4xl mx-auto space-y-4">
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Template Configuration</CardTitle>
                                <CardDescription className="text-sm">
                                    Essential settings for your prompt template
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {/* Template Name */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-name">Template Name *</Label>
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

                                {/* Category */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-category">Category</Label>
                                    <Select
                                        value={config.category || 'none'}
                                        onValueChange={(value) =>
                                            updateConfig({ category: value === 'none' ? undefined : value })
                                        }
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select category" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">No Category</SelectItem>
                                            <SelectItem value="Development">Development</SelectItem>
                                            <SelectItem value="Analysis">Analysis</SelectItem>
                                            <SelectItem value="Documentation">Documentation</SelectItem>
                                            <SelectItem value="Communication">Communication</SelectItem>
                                            <SelectItem value="Testing">Testing</SelectItem>
                                            <SelectItem value="Other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* Command */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-command">Command (Optional)</Label>
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
                                        Shorthand command for quick access (letters, numbers, hyphens, underscores only)
                                    </p>
                                </div>

                                {/* Prompt Text */}
                                <div className="space-y-2">
                                    <Label htmlFor="template-prompt">Prompt Text *</Label>
                                    <Textarea
                                        id="template-prompt"
                                        placeholder="Enter your prompt template here. Use {{variable_name}} for placeholders."
                                        value={config.prompt_text || ''}
                                        onChange={(e) => updateConfig({ prompt_text: e.target.value })}
                                        rows={12}
                                        className={`font-mono ${validationErrors.prompt_text ? 'border-red-500' : ''}`}
                                    />
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

                                {/* Detected Variables */}
                                {config.detected_variables && config.detected_variables.length > 0 && (
                                    <div className="space-y-2 pt-3 border-t">
                                        <Label>Detected Variables ({config.detected_variables.length})</Label>
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
                                )}
                            </CardContent>
                        </Card>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer Actions */}
            <div className="flex justify-end gap-2 p-4 border-t">
                <Button variant="outline" onClick={handleClose} disabled={isLoading}>
                    Cancel
                </Button>
                <Button
                    onClick={handleSave}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Saving...
                        </>
                    ) : (
                        'Save'
                    )}
                </Button>
            </div>
        </div>
    );
};