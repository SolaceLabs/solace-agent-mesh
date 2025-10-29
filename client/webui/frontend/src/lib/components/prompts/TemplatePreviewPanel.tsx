import React from 'react';
import { Edit, CheckCircle, FileText } from 'lucide-react';
import { Button, Badge, Card, CardContent, CardHeader, CardTitle } from '@/lib/components/ui';
import type { TemplateConfig } from './hooks/usePromptTemplateBuilder';

interface TemplatePreviewPanelProps {
    config: TemplateConfig;
    onEditManually: () => void;
    highlightedFields: string[];
    isReadyToSave: boolean;
}

export const TemplatePreviewPanel: React.FC<TemplatePreviewPanelProps> = ({
    config,
    onEditManually,
    highlightedFields,
    isReadyToSave,
}) => {
    const hasContent = config.name || config.prompt_text;

    const renderField = (label: string, value: string | undefined, fieldName: string) => {
        const isHighlighted = highlightedFields.includes(fieldName);
        const isEmpty = !value || value.trim().length === 0;

        return (
            <div
                className={`space-y-1 p-3 rounded-lg transition-all duration-300 ${
                    isHighlighted ? 'bg-primary/10 ring-2 ring-primary' : 'bg-muted/50'
                }`}
            >
                <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">{label}</label>
                    {isHighlighted && (
                        <Badge variant="default" className="text-xs">
                            Updated
                        </Badge>
                    )}
                </div>
                <div className={`text-sm ${isEmpty ? 'text-muted-foreground italic' : ''}`}>
                    {isEmpty ? `No ${label.toLowerCase()} yet` : value}
                </div>
            </div>
        );
    };

    const renderPromptText = () => {
        const isHighlighted = highlightedFields.includes('prompt_text');
        const isEmpty = !config.prompt_text || config.prompt_text.trim().length === 0;

        // Highlight variables in the prompt text
        const highlightVariables = (text: string) => {
            const parts = text.split(/(\{\{[^}]+\}\})/g);
            return parts.map((part, index) => {
                if (part.match(/\{\{[^}]+\}\}/)) {
                    return (
                        <span key={index} className="bg-primary/20 text-primary font-medium px-1 rounded">
                            {part}
                        </span>
                    );
                }
                return <span key={index}>{part}</span>;
            });
        };

        return (
            <div
                className={`space-y-1 p-3 rounded-lg transition-all duration-300 ${
                    isHighlighted ? 'bg-primary/10 ring-2 ring-primary' : 'bg-muted/50'
                }`}
            >
                <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Prompt Text</label>
                    {isHighlighted && (
                        <Badge variant="default" className="text-xs">
                            Updated
                        </Badge>
                    )}
                </div>
                <div
                    className={`text-sm whitespace-pre-wrap font-mono ${
                        isEmpty ? 'text-muted-foreground italic' : ''
                    }`}
                >
                    {isEmpty ? 'No prompt text yet' : highlightVariables(config.prompt_text!)}
                </div>
            </div>
        );
    };

    const renderVariables = () => {
        const variables = config.detected_variables || [];
        const isHighlighted = highlightedFields.includes('detected_variables');

        if (variables.length === 0) {
            return (
                <div className="text-sm text-muted-foreground italic p-3 bg-muted/50 rounded-lg">
                    No variables detected yet
                </div>
            );
        }

        return (
            <div
                className={`p-3 rounded-lg transition-all duration-300 ${
                    isHighlighted ? 'bg-primary/10 ring-2 ring-primary' : 'bg-muted/50'
                }`}
            >
                <div className="flex flex-wrap gap-2">
                    {variables.map((variable, index) => (
                        <Badge key={index} variant="secondary" className="font-mono">
                            {`{{${variable}}}`}
                        </Badge>
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 px-4 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
                            <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-sm">Template Preview</h3>
                            <p className="text-xs text-muted-foreground">
                                Live preview of your template
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {isReadyToSave && (
                            <Badge variant="default" className="animate-pulse">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                Ready to Save
                            </Badge>
                        )}
                        <Button
                            onClick={onEditManually}
                            variant="outline"
                            size="sm"
                            disabled={!hasContent}
                        >
                            <Edit className="h-3 w-3 mr-1" />
                            Edit Manually
                        </Button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {!hasContent ? (
                    <div className="flex flex-col items-center justify-center h-full text-center p-8">
                        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
                            <FileText className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="font-semibold text-lg mb-2">No Template Yet</h3>
                        <p className="text-sm text-muted-foreground max-w-sm">
                            Start chatting with the AI assistant to create your template. The preview
                            will update in real-time as you describe your task.
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Basic Info */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Basic Information</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {renderField('Template Name', config.name, 'name')}
                                {renderField('Description', config.description, 'description')}
                                {renderField('Category', config.category, 'category')}
                                {renderField('Command', config.command ? `/${config.command}` : undefined, 'command')}
                            </CardContent>
                        </Card>

                        {/* Prompt Text */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Prompt Template</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {renderPromptText()}
                            </CardContent>
                        </Card>

                        {/* Variables */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base flex items-center gap-2">
                                    Detected Variables
                                    {config.detected_variables && config.detected_variables.length > 0 && (
                                        <Badge variant="secondary" className="text-xs">
                                            {config.detected_variables.length}
                                        </Badge>
                                    )}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {renderVariables()}
                            </CardContent>
                        </Card>

                        {/* Validation Status */}
                        {config.name && config.prompt_text && (
                            <Card className="border-green-200 dark:border-green-900 bg-green-50 dark:bg-green-950/20">
                                <CardContent className="pt-6">
                                    <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                                        <CheckCircle className="h-5 w-5" />
                                        <span className="text-sm font-medium">
                                            Template looks good! Ready to save.
                                        </span>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </>
                )}
            </div>

        </div>
    );
};