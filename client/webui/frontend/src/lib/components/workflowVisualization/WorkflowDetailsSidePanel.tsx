import React, { useState, useCallback, useMemo } from "react";
import yaml from "js-yaml";
import { X, Workflow, Copy, Check, Code } from "lucide-react";

import type { AgentCardInfo } from "@/lib/types";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui/tabs";
import { MarkdownHTMLConverter } from "@/lib/components/common";
import { JSONViewer } from "@/lib/components/jsonViewer";

export type WorkflowPanelView = "details" | "code";

interface WorkflowDetailsSidePanelProps {
    workflow: AgentCardInfo | null;
    config: WorkflowConfig | null;
    view: WorkflowPanelView;
    onClose: () => void;
    onViewChange: (view: WorkflowPanelView) => void;
}

/**
 * Side panel for showing workflow-level details or raw YAML code.
 * Replaces the former modal-based workflow details view.
 */
const WorkflowDetailsSidePanel: React.FC<WorkflowDetailsSidePanelProps> = ({
    workflow,
    config,
    view,
    onClose,
    onViewChange,
}) => {
    const [activeTab, setActiveTab] = useState<"input" | "output">("input");
    const [isCopied, setIsCopied] = useState(false);

    // Generate YAML string from config
    const yamlString = useMemo(() => {
        if (!config) return "";
        try {
            return yaml.dump(config, { indent: 2, lineWidth: -1 });
        } catch {
            return "Unable to generate YAML";
        }
    }, [config]);

    // Handle copy to clipboard
    const handleCopy = useCallback(() => {
        if (!yamlString) return;
        navigator.clipboard.writeText(yamlString);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    }, [yamlString]);

    if (!workflow || !config) {
        return null;
    }

    const description = config.description || workflow.description;
    const title = workflow.displayName || workflow.name;

    // Handle toggling to code view
    const handleInspectCode = useCallback(() => {
        onViewChange("code");
    }, [onViewChange]);

    // Handle toggling back to details view
    const handleShowDetails = useCallback(() => {
        onViewChange("details");
    }, [onViewChange]);

    return (
        <div className="flex h-full flex-col bg-white dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-[var(--color-brand-wMain)]" />
                    <span className="font-medium text-gray-900 dark:text-gray-100">{title}</span>
                </div>
                <div className="flex items-center gap-2">
                    {view === "details" ? (
                        <button
                            onClick={handleInspectCode}
                            className="flex items-center gap-1.5 text-sm text-[var(--color-brand-wMain)] hover:underline"
                        >
                            <Code className="h-4 w-4" />
                            Inspect Code
                        </button>
                    ) : (
                        <button
                            onClick={handleShowDetails}
                            className="flex items-center gap-1.5 text-sm text-[var(--color-brand-wMain)] hover:underline"
                        >
                            <Workflow className="h-4 w-4" />
                            Show Details
                        </button>
                    )}
                    <button
                        onClick={onClose}
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>

            {/* Toolbar (only for code view) */}
            {view === "code" && (
                <div className="flex items-center justify-end gap-1 border-b border-gray-200 px-3 py-2 dark:border-gray-700">
                    <button
                        onClick={handleCopy}
                        className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
                        title="Copy YAML"
                    >
                        {isCopied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                    </button>
                </div>
            )}

            {/* Content */}
            <div className="scrollbar-themed flex-1 overflow-y-auto p-4">
                {view === "code" ? (
                    /* Raw YAML Code View */
                    <pre className="scrollbar-themed overflow-auto rounded-lg bg-gray-100 p-3 font-mono text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                        {yamlString}
                    </pre>
                ) : (
                    /* Workflow Details View */
                    <>
                        {/* Version */}
                        {config.version && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Version
                                </label>
                                <div className="text-sm text-gray-900 dark:text-gray-100">{config.version}</div>
                            </div>
                        )}

                        {/* Description */}
                        {description && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Description
                                </label>
                                <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                                    <MarkdownHTMLConverter>{description}</MarkdownHTMLConverter>
                                </div>
                            </div>
                        )}

                        {/* Schemas Section */}
                        {(config.input_schema || config.output_schema || config.output_mapping) && (
                            <div className="mt-4">
                                <Tabs
                                    value={activeTab}
                                    onValueChange={value => setActiveTab(value as "input" | "output")}
                                >
                                    <TabsList className="mb-3 w-full">
                                        <TabsTrigger value="input" className="flex-1">
                                            Input
                                        </TabsTrigger>
                                        <TabsTrigger value="output" className="flex-1">
                                            Output
                                        </TabsTrigger>
                                    </TabsList>

                                    <TabsContent value="input" className="mt-0">
                                        {config.input_schema ? (
                                            <div className="max-h-64 overflow-auto rounded-lg border">
                                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                <JSONViewer
                                                    data={config.input_schema as any}
                                                    maxDepth={3}
                                                    className="border-none text-xs"
                                                />
                                            </div>
                                        ) : (
                                            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                                No input schema defined
                                            </div>
                                        )}
                                    </TabsContent>

                                    <TabsContent value="output" className="mt-0 space-y-4">
                                        {/* Output Schema */}
                                        <div>
                                            <label className="mb-2 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                                Schema
                                            </label>
                                            {config.output_schema ? (
                                                <div className="max-h-48 overflow-auto rounded-lg border">
                                                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                    <JSONViewer
                                                        data={config.output_schema as any}
                                                        maxDepth={3}
                                                        className="border-none text-xs"
                                                    />
                                                </div>
                                            ) : (
                                                <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                                    No output schema defined
                                                </div>
                                            )}
                                        </div>

                                        {/* Output Mapping */}
                                        {config.output_mapping && (
                                            <div>
                                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                                    Output Mapping
                                                </label>
                                                <div className="text-muted-foreground mb-2 text-xs">
                                                    Defines how the final agent output is mapped to the workflow output
                                                    schema.
                                                </div>
                                                <div className="max-h-48 overflow-auto rounded-lg border">
                                                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                    <JSONViewer
                                                        data={config.output_mapping as any}
                                                        maxDepth={3}
                                                        className="border-none text-xs"
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </TabsContent>
                                </Tabs>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default WorkflowDetailsSidePanel;
