import React, { useRef } from "react";
import { NotepadText } from "lucide-react";
import { Badge, CardTitle, Label } from "@/lib/components/ui";
import type { TemplateConfig } from "@/lib/types";

interface TemplatePreviewPanelProps {
    config: TemplateConfig;
    highlightedFields: string[];
    isReadyToSave: boolean;
}

export const TemplatePreviewPanel: React.FC<TemplatePreviewPanelProps> = ({ config, highlightedFields }) => {
    // Only show content when we have actual prompt text, not just metadata
    const hasContent = config.promptText && config.promptText.trim().length > 0;

    const updateCountRef = useRef(0);
    const lastHighlightedFieldsRef = useRef<string[]>([]);

    // Check if highlightedFields actually changed (not just a re-render)
    const highlightedFieldsChanged = highlightedFields.length > 0 && (highlightedFields.length !== lastHighlightedFieldsRef.current.length || highlightedFields.some((f, i) => f !== lastHighlightedFieldsRef.current[i]));

    // Update count when we get new highlighted fields with content
    if (highlightedFieldsChanged && hasContent) {
        updateCountRef.current += 1;
        lastHighlightedFieldsRef.current = [...highlightedFields];
    }

    // Show badges only after the first update (updateCount >= 2 means we've had at least one update after initial generation)
    const showBadges = updateCountRef.current >= 2 && highlightedFields.length > 0;

    const renderField = (label: string, value: string | undefined, fieldName: string, isCommand: boolean = false) => {
        const isHighlighted = highlightedFields.includes(fieldName);
        const isEmpty = !value || value.trim().length === 0;

        return (
            <div className="space-y-2">
                <div className="flex items-center gap-2">
                    <Label className="text-muted-foreground text-sm font-medium">{label}</Label>
                    {isHighlighted && showBadges && (
                        <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                            Updated
                        </Badge>
                    )}
                </div>
                {isCommand ? (
                    <div className="rounded p-3 text-sm">{isEmpty ? <span className="text-muted-foreground italic">No {label.toLowerCase()} yet</span> : <span className="text-primary font-mono">/{value}</span>}</div>
                ) : (
                    <div className="rounded p-3 text-sm">{isEmpty ? <span className="text-muted-foreground italic">No {label.toLowerCase()} yet</span> : value}</div>
                )}
            </div>
        );
    };

    const renderPromptText = () => {
        const isHighlighted = highlightedFields.includes("promptText");
        const isEmpty = !config.promptText || config.promptText.trim().length === 0;

        // Highlight variables in the prompt text
        const highlightVariables = (text: string) => {
            const parts = text.split(/(\{\{[^}]+\}\})/g);
            return parts.map((part, index) => {
                if (part.match(/\{\{[^}]+\}\}/)) {
                    return (
                        <span key={index} className="bg-primary/20 text-primary rounded px-1 font-medium">
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
                        <Badge variant="default" className="bg-primary text-primary-foreground text-xs">
                            Updated
                        </Badge>
                    )}
                </div>
                <div className="min-h-[288px] w-full rounded-md px-3 py-2 font-mono text-sm whitespace-pre-wrap">{isEmpty ? <span className="text-muted-foreground italic">No prompt text yet</span> : highlightVariables(config.promptText!)}</div>
            </div>
        );
    };

    const renderVariables = () => {
        const variables = config.detected_variables || [];

        if (variables.length === 0) {
            return <div className="text-muted-foreground py-2 text-sm italic">No variables detected yet</div>;
        }

        return (
            <div className="py-2">
                <div className="flex flex-wrap gap-2">
                    {variables.map((variable, index) => (
                        <span key={index} className="bg-primary/10 text-primary rounded px-2 py-1 font-mono text-xs">
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
                    <div className="bg-muted flex h-8 w-8 items-center justify-center rounded-full">
                        <NotepadText className="text-muted-foreground h-4 w-4" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold">Template Preview</h3>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 space-y-4 overflow-y-auto px-4" style={{ paddingTop: "24px" }}>
                {!hasContent ? (
                    <div className="flex h-full flex-col items-center justify-center p-8 text-center">
                        <div className="bg-muted mb-4 flex h-16 w-16 items-center justify-center rounded-full">
                            <NotepadText className="text-muted-foreground h-8 w-8" />
                        </div>
                        <h3 className="mb-2 text-lg font-semibold">No Template Yet</h3>
                        <p className="text-muted-foreground max-w-sm text-sm">Start chatting with the AI assistant to create your template. The preview will update in real-time as you describe your task.</p>
                    </div>
                ) : (
                    <>
                        {/* Basic Info */}
                        <div>
                            <CardTitle className="mb-4 text-base">Basic Information</CardTitle>
                            <div className="space-y-6">
                                {renderField("Name", config.name, "name")}
                                {renderField("Description", config.description, "description")}
                                {renderField("Tag", config.category, "category")}
                                {renderField("Chat Shortcut", config.command, "command", true)}
                            </div>
                        </div>

                        {/* Content */}
                        <div>
                            <CardTitle className="mb-4 text-base">Content</CardTitle>
                            {renderPromptText()}
                        </div>

                        {/* Variables */}
                        <div>
                            <CardTitle className="mb-4 text-base">Variables</CardTitle>
                            <div className="space-y-3">
                                {config.detected_variables && config.detected_variables.length > 0 ? (
                                    <>
                                        <p className="text-muted-foreground text-sm leading-relaxed">
                                            Variables are placeholder values that make your prompt flexible and reusable. Variables are enclosed in double brackets like{" "}
                                            <code className="bg-muted rounded px-1.5 py-0.5 font-mono text-xs">{"{{Variable Name}}"}</code>. You will be asked to fill in these variable values whenever you use this prompt. The prompt above has the
                                            following variables:
                                        </p>
                                        {renderVariables()}
                                    </>
                                ) : (
                                    <div className="text-muted-foreground bg-muted/50 rounded-lg p-3 text-sm italic">No variables detected yet</div>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
