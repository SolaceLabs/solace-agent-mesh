import React, { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
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
import { Sparkles, CheckCircle, Loader2, AlertCircle, Check } from 'lucide-react';
import { usePromptTemplateBuilder } from './hooks/usePromptTemplateBuilder';
import { PromptBuilderChat } from './PromptBuilderChat';
import { TemplatePreviewPanel } from './TemplatePreviewPanel';

interface PromptTemplateBuilderProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: () => void;
}

export const PromptTemplateBuilder: React.FC<PromptTemplateBuilderProps> = ({
    isOpen,
    onClose,
    onSuccess,
}) => {
    const {
        config,
        updateConfig,
        validateConfig,
        saveTemplate,
        resetConfig,
        validationErrors,
        isLoading,
    } = usePromptTemplateBuilder();

    const [builderMode, setBuilderMode] = useState<'manual' | 'ai-assisted'>('ai-assisted');
    const [isReadyToSave, setIsReadyToSave] = useState(false);
    const [highlightedFields, setHighlightedFields] = useState<string[]>([]);
    const [showValidationSuccess, setShowValidationSuccess] = useState(false);

    const handleClose = () => {
        resetConfig();
        setBuilderMode('ai-assisted');
        setIsReadyToSave(false);
        setHighlightedFields([]);
        onClose();
    };

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
        }, 3000);
    };

    const handleSwitchToManual = () => {
        setBuilderMode('manual');
    };

    const handleValidate = async () => {
        const isValid = await validateConfig();
        if (isValid) {
            setShowValidationSuccess(true);
            setTimeout(() => setShowValidationSuccess(false), 3000);
        }
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
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="!w-[75vw] !max-w-[1400px] max-h-[90vh]">
                <DialogHeader>
                    <div className="flex items-center justify-between gap-4">
                        <DialogTitle className="flex items-center gap-2">
                            <Sparkles className="h-5 w-5" />
                            Create Prompt Template
                        </DialogTitle>
                        <ModeSelector />
                    </div>
                </DialogHeader>

                {builderMode === 'ai-assisted' ? (
                    /* AI-Assisted Mode - Split View */
                    <div className="flex gap-4 h-[calc(90vh-180px)]">
                        <div className="w-[60%] border rounded-lg overflow-hidden">
                            <TemplatePreviewPanel
                                config={config}
                                onEditManually={handleSwitchToManual}
                                highlightedFields={highlightedFields}
                                isReadyToSave={isReadyToSave}
                            />
                        </div>
                        <div className="w-[40%] border rounded-lg overflow-hidden">
                            <PromptBuilderChat
                                onConfigUpdate={handleConfigUpdate}
                                currentConfig={config}
                                onReadyToSave={setIsReadyToSave}
                            />
                        </div>
                    </div>
                ) : (
                    /* Manual Mode - Form View */
                    <div className="space-y-4 max-h-[calc(90vh-180px)] overflow-y-auto px-1">
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
                )}

                {/* Footer Actions */}
                <div className="flex justify-between pt-6 border-t">
                    <Button variant="outline" onClick={handleClose} disabled={isLoading}>
                        Cancel
                    </Button>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            onClick={handleValidate}
                            disabled={isLoading}
                            className={showValidationSuccess ? 'border-green-500 text-green-600' : ''}
                        >
                            {showValidationSuccess ? (
                                <>
                                    <Check className="h-4 w-4 mr-2" />
                                    Valid!
                                </>
                            ) : (
                                'Validate'
                            )}
                        </Button>
                        <Button
                            onClick={handleSave}
                            disabled={isLoading || !config.name || !config.prompt_text}
                            className={isReadyToSave && builderMode === 'ai-assisted' ? 'animate-pulse' : ''}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                <>
                                    <CheckCircle className="h-4 w-4 mr-2" />
                                    Save Template
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};