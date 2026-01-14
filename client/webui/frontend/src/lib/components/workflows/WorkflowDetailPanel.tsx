import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import yaml from "js-yaml";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig, getWorkflowNodeCount } from "@/lib/utils/agentUtils";
import { Button } from "@/lib/components/ui/button";
import { MarkdownHTMLConverter } from "@/lib/components/common";
import { JSONViewer } from "@/lib/components/jsonViewer";
import { Workflow, GitMerge, FileJson, X, ExternalLink, ChevronDown, ChevronUp, FileText, Code, Copy, Check } from "lucide-react";

interface WorkflowDetailPanelProps {
    workflow: AgentCardInfo;
    /** Optional config - if not provided, will be computed from workflow */
    config?: ReturnType<typeof getWorkflowConfig>;
    onClose: () => void;
    /** Whether to show the "Open Workflow" button (default: true) */
    showOpenButton?: boolean;
}

export const WorkflowDetailPanel: React.FC<WorkflowDetailPanelProps> = ({
    workflow,
    config: providedConfig,
    onClose,
    showOpenButton = true,
}) => {
    const navigate = useNavigate();
    const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false);
    const [showExpandButton, setShowExpandButton] = useState(false);
    const [showCodeView, setShowCodeView] = useState(false);
    const [isCopied, setIsCopied] = useState(false);
    const descriptionRef = useRef<HTMLDivElement>(null);

    const config = providedConfig ?? getWorkflowConfig(workflow);
    const nodeCount = getWorkflowNodeCount(workflow);
    const description = config?.description || workflow.description;

    // Handle copy to clipboard
    const handleCopy = useCallback(() => {
        if (!config) return;
        try {
            const yamlStr = yaml.dump(config, { indent: 2, lineWidth: -1 });
            navigator.clipboard.writeText(yamlStr);
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    }, [config]);

    // Reset expansion state when workflow changes
    useEffect(() => {
        setIsDescriptionExpanded(false);
    }, [workflow.name]);

    // Check if description needs truncation (more than 5 lines)
    useEffect(() => {
        if (descriptionRef.current) {
            const element = descriptionRef.current;
            // Check if content is taller than 5 lines (approximately 5 * line-height)
            const lineHeight = parseInt(getComputedStyle(element).lineHeight) || 20;
            const maxHeight = lineHeight * 5;
            setShowExpandButton(element.scrollHeight > maxHeight + 5); // +5 for tolerance
        }
    }, [description]);

    const handleOpenWorkflow = () => {
        navigate(`/agents/workflows/${encodeURIComponent(workflow.name)}`);
    };

    return (
        <div className="flex h-full flex-col bg-white dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-[var(--color-brand-wMain)]" />
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                        {workflow.displayName || workflow.name}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    {/* View toggle */}
                    <div className="flex overflow-hidden rounded-md border border-gray-300 dark:border-gray-600">
                        <button
                            onClick={() => setShowCodeView(false)}
                            className={`flex items-center justify-center px-3 py-1.5 ${
                                !showCodeView
                                    ? "bg-[var(--color-brand-wMain)]/10 text-gray-700 dark:text-gray-200"
                                    : "bg-white text-gray-500 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                            }`}
                            title="Details view"
                        >
                            <FileText className="h-4 w-4" />
                        </button>
                        <button
                            onClick={() => setShowCodeView(true)}
                            className={`flex items-center justify-center border-l border-gray-300 px-3 py-1.5 dark:border-gray-600 ${
                                showCodeView
                                    ? "bg-[var(--color-brand-wMain)]/10 text-gray-700 dark:text-gray-200"
                                    : "bg-white text-gray-500 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                            }`}
                            title="Code view"
                        >
                            <Code className="h-4 w-4" />
                        </button>
                    </div>
                    <button
                        onClick={onClose}
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>

            {/* Toolbar (only for code view) */}
            {showCodeView && (
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
                {showCodeView ? (
                    // Code view - show YAML
                    config ? (
                        <pre className="scrollbar-themed overflow-auto rounded-lg bg-gray-100 p-3 font-mono text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                            {yaml.dump(config, { indent: 2, lineWidth: -1 })}
                        </pre>
                    ) : (
                        <div className="text-muted-foreground text-sm">No configuration available</div>
                    )
                ) : (
                    <>
                        {/* Version and Node Count */}
                        <div className="mb-4 flex items-center gap-4">
                    <div>
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Version
                        </label>
                        <div className="flex items-center gap-1 text-sm text-gray-900 dark:text-gray-100">
                            <GitMerge size={14} className="text-gray-400" />
                            {workflow.version || "N/A"}
                        </div>
                    </div>
                    <div>
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Nodes
                        </label>
                        <div className="flex items-center gap-1 text-sm text-gray-900 dark:text-gray-100">
                            <Workflow size={14} className="text-gray-400" />
                            {nodeCount > 0 ? nodeCount : "N/A"}
                        </div>
                    </div>
                </div>

                {/* Description */}
                {description && (
                    <div className="mb-4">
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Description
                        </label>
                        <div
                            ref={descriptionRef}
                            className={`prose prose-sm dark:prose-invert max-w-none text-sm text-gray-700 dark:text-gray-300 ${
                                !isDescriptionExpanded && showExpandButton ? "line-clamp-5" : ""
                            }`}
                        >
                            <MarkdownHTMLConverter>{description}</MarkdownHTMLConverter>
                        </div>
                        {showExpandButton && (
                            <button
                                onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                                className="mt-2 flex items-center gap-1 text-sm text-[var(--color-brand-wMain)] hover:underline"
                            >
                                {isDescriptionExpanded ? (
                                    <>
                                        <ChevronUp className="h-4 w-4" />
                                        Show Less
                                    </>
                                ) : (
                                    <>
                                        <ChevronDown className="h-4 w-4" />
                                        Show More
                                    </>
                                )}
                            </button>
                        )}
                    </div>
                )}

                {/* Open Workflow button */}
                {showOpenButton && (
                    <div className="mb-4">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleOpenWorkflow}
                            className="w-full"
                        >
                            <ExternalLink className="mr-2 h-4 w-4" />
                            Open Workflow
                        </Button>
                    </div>
                )}

                {/* Input Schema */}
                {config?.input_schema && (
                    <div className="mb-4">
                        <label className="mb-2 flex items-center text-xs font-medium text-gray-500 dark:text-gray-400">
                            <FileJson size={14} className="mr-1" />
                            Input Schema
                        </label>
                        <div className="max-h-48 overflow-auto rounded-lg border">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            <JSONViewer data={config.input_schema as any} maxDepth={2} className="border-none text-xs" />
                        </div>
                    </div>
                )}

                {/* Output Schema */}
                {config?.output_schema && (
                    <div className="mb-4">
                        <label className="mb-2 flex items-center text-xs font-medium text-gray-500 dark:text-gray-400">
                            <FileJson size={14} className="mr-1" />
                            Output Schema
                        </label>
                        <div className="max-h-48 overflow-auto rounded-lg border">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            <JSONViewer data={config.output_schema as any} maxDepth={2} className="border-none text-xs" />
                        </div>
                    </div>
                )}

                {/* Output Mapping */}
                {config?.output_mapping && (
                    <div className="mb-4">
                        <label className="mb-1 flex items-center text-xs font-medium text-gray-500 dark:text-gray-400">
                            <FileJson size={14} className="mr-1" />
                            Output Mapping
                        </label>
                        <div className="text-muted-foreground mb-2 text-xs">
                            Defines how the final agent output is mapped to the workflow output schema.
                        </div>
                        <div className="max-h-48 overflow-auto rounded-lg border">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            <JSONViewer data={config.output_mapping as any} maxDepth={2} className="border-none text-xs" />
                        </div>
                    </div>
                )}

                {/* Provider */}
                {workflow.provider && (
                    <div className="border-t pt-4">
                        <label className="mb-2 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Provider
                        </label>
                        <div className="space-y-2 text-sm">
                            {workflow.provider.organization && (
                                <div className="text-gray-700 dark:text-gray-300">
                                    <span className="text-gray-500 dark:text-gray-400">Organization:</span>{" "}
                                    {workflow.provider.organization}
                                </div>
                            )}
                            {workflow.provider.url && (
                                <div className="text-gray-700 dark:text-gray-300">
                                    <span className="text-gray-500 dark:text-gray-400">URL:</span>{" "}
                                    <a
                                        href={workflow.provider.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-[var(--color-brand-wMain)] hover:underline"
                                    >
                                        {workflow.provider.url}
                                    </a>
                                </div>
                            )}
                        </div>
                    </div>
                )}
                    </>
                )}
            </div>
        </div>
    );
};
