import React, { useRef, useEffect } from 'react';
import { FileText } from 'lucide-react';
import { Badge, CardTitle, Label } from '@/lib/components/ui';
import type { TemplateConfig } from './hooks/usePromptTemplateBuilder';

interface TemplatePreviewPanelProps {
    config: TemplateConfig;
    highlightedFields: string[];
    isReadyToSave: boolean;
}

export const TemplatePreviewPanel: React.FC<TemplatePreviewPanelProps> = ({
    config,
    highlightedFields,
}) => {
    // Only show content when we have actual prompt text, not just metadata
    const hasContent = config.prompt_text && config.prompt_text.trim().length > 0;
    
    // Track if we've ever had content before to distinguish initial generation from updates
    const hadContentBeforeRef = useRef(false);
    const previousHighlightedFieldsRef = useRef<string[]>([]);
    
    useEffect(() => {
        // When highlightedFields changes, check if we had content before
        if (highlightedFields.length > 0 && hasContent) {
            if (!hadContentBeforeRef.current) {
                hadContentBeforeRef.current = true;
            }
        }
        previousHighlightedFieldsRef.current = highlightedFields;
    }, [highlightedFields, hasContent]);
    
    const showBadges = hadContentBeforeRef.current && highlightedFields.length > 0;

    const renderField = (label: string, value: string | undefined, fieldName: string, isCommand: boolean = false) => {
        const isHighlighted = highlightedFields.includes(fieldName);
        const isEmpty = !value || value.trim().length === 0;

        return (
            <div className="space-y-2">
                <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium text-muted-foreground">{label}</Label>
                    {isHighlighted && showBadges && (
                        <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                            Updated
                        </Badge>
                    )}
                </div>
                {isCommand ? (
                    <div className="text-sm p-3 rounded">
                        {isEmpty ? (
                            <span className="text-muted-foreground italic">No {label.toLowerCase()} yet</span>
                        ) : (
                            <span className="font-mono text-primary">/{value}</span>
                        )}
                    </div>
                ) : (
                    <div className="text-sm p-3 rounded">
                        {isEmpty ? (
                            <span className="text-muted-foreground italic">No {label.toLowerCase()} yet</span>
                        ) : (
                            value
                        )}
                    </div>
                )}
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
            <div className="space-y-2">
                <div className="flex items-center gap-2">
                    {isHighlighted && showBadges && (
                        <Badge variant="default" className="text-xs bg-primary text-primary-foreground">
                            Updated
                        </Badge>
                    )}
                </div>
                <div className="min-h-[288px] w-full rounded-md px-3 py-2 text-sm font-mono whitespace-pre-wrap">
                    {isEmpty ? (
                        <span className="text-muted-foreground italic">No prompt text yet</span>
                    ) : (
                        highlightVariables(config.prompt_text!)
                    )}
                </div>
            </div>
        );
    };

    const renderVariables = () => {
        const variables = config.detected_variables || [];

        if (variables.length === 0) {
            return (
                <div className="text-sm text-muted-foreground italic py-2">
                    No variables detected yet
                </div>
            );
        }

        return (
            <div className="py-2">
                <div className="flex flex-wrap gap-2">
                    {variables.map((variable, index) => (
                        <span
                            key={index}
                            className="px-2 py-1 bg-primary/10 text-primary text-xs font-mono rounded"
                        >
                            {`{{${variable}}}`}
                        </span>
                    ))}
                </div>
            </div>
        );
    };

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-sm">Template Preview</h3>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-4 space-y-4" style={{ paddingTop: '24px' }}>
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
                        <div>
                            <CardTitle className="text-base mb-4">Basic Information</CardTitle>
                            <div className="space-y-6">
                                {renderField('Name', config.name, 'name')}
                                {renderField('Description', config.description, 'description')}
                                {renderField('Tag', config.category, 'category')}
                                {renderField('Chat Shortcut', config.command, 'command', true)}
                            </div>
                        </div>

                        {/* Content */}
                        <div>
                            <CardTitle className="text-base mb-4">Content</CardTitle>
                            {renderPromptText()}
                        </div>

                        {/* Variables */}
                        <div>
                            <CardTitle className="text-base mb-4">Variables</CardTitle>
                            <div className="space-y-3">
                                {config.detected_variables && config.detected_variables.length > 0 ? (
                                    <>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            Variables are placeholder values that make your prompt flexible and reusable. Variables are enclosed in double brackets like <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{'{{Variable Name}}'}</code>. You will be asked to fill in these variable values whenever you use this prompt. The prompt above has the following variables:
                                        </p>
                                        {renderVariables()}
                                    </>
                                ) : (
                                    <div className="text-sm text-muted-foreground italic p-3 bg-muted/50 rounded-lg">
                                        No variables detected yet
                                    </div>
                                )}
                            </div>
                        </div>

                    </>
                )}
            </div>

        </div>
    );
};