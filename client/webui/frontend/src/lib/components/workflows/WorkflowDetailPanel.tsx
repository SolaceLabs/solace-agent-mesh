import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import yaml from "js-yaml";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig, getWorkflowNodeCount } from "@/lib/utils/agentUtils";
import { Button } from "@/lib/components/ui/button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui/tooltip";
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
    const [activeTab, setActiveTab] = useState<"input" | "output">("input");
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
        <div className="flex h-full flex-col border-l border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex min-w-0 items-center gap-2">
                    <Workflow className="h-5 w-5 flex-shrink-0 text-(--color-brand-wMain)" />
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <span className="truncate text-xl font-semibold">
                                {workflow.displayName || workflow.name}
                            </span>
                        </TooltipTrigger>
                        <TooltipContent>
                            {workflow.displayName || workflow.name}
                        </TooltipContent>
                    </Tooltip>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onClose}
                    tooltip="Close"
                >
                    <X className="h-5 w-5" />
                </Button>
            </div>

            {/* Content */}
            <div className="scrollbar-themed flex-1 overflow-y-auto p-4">
                {showCodeView ? (
                    // Code view - show YAML
                    config ? (
                        <div className="relative h-full">
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={handleCopy}
                                tooltip={isCopied ? "Copied!" : "Copy"}
                                className="absolute right-2 top-2 z-10 h-8 w-8"
                            >
                                {isCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                            </Button>
                            <pre className="scrollbar-themed h-full overflow-auto rounded-lg bg-gray-100 p-3 font-mono text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                                {yaml.dump(config, { indent: 2, lineWidth: -1 })}
                            </pre>
                        </div>
                    ) : (
                        <div className="text-muted-foreground text-sm">No configuration available</div>
                    )
                ) : (
                    <>
                        {/* Version and Node Count */}
                        <div className="mb-4 grid grid-cols-2 gap-4">
                    <div>
                        <label className="mb-1 block text-sm font-medium text-gray-500 dark:text-gray-400">
                            Version
                        </label>
                        <div className="text-sm text-gray-900 dark:text-gray-100">
                            {workflow.version || "N/A"}
                        </div>
                    </div>
                    <div>
                        <label className="mb-1 block text-sm font-medium text-gray-500 dark:text-gray-400">
                            Nodes
                        </label>
                        <div className="text-sm text-gray-900 dark:text-gray-100">
                            {nodeCount > 0 ? nodeCount : "N/A"}
                        </div>
                    </div>
                </div>

                {/* Description */}
                {description && (
                    <div className="mb-4">
                        <label className="mb-1 block text-sm font-medium text-gray-500 dark:text-gray-400">
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
                            <Button
                                variant="link"
                                onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                                className="mt-2 h-auto pl-0 pr-0 text-sm"
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
                            </Button>
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
                            Open Workflow
                        </Button>
                    </div>
                )}

                {/* Input/Output Schema Tabs */}
                {(config?.input_schema || config?.output_schema) && (
                    <div className="mb-4">
                        {/* Tab buttons */}
                        <div className="mb-3 flex border-b" role="tablist">
                            <button
                                role="tab"
                                aria-selected={activeTab === "input"}
                                onClick={() => setActiveTab("input")}
                                className={`relative px-4 py-2 font-medium transition-colors ${
                                    activeTab === "input"
                                        ? "border-b-2 border-(--color-brand-wMain) font-semibold"
                                        : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
                                }`}
                            >
                                Input
                            </button>
                            <button
                                role="tab"
                                aria-selected={activeTab === "output"}
                                onClick={() => setActiveTab("output")}
                                className={`relative px-4 py-2 font-medium transition-colors ${
                                    activeTab === "output"
                                        ? "border-b-2 border-(--color-brand-wMain) font-semibold"
                                        : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200"
                                }`}
                            >
                                Output
                            </button>
                        </div>

                        {/* Tab content */}
                        <div className="mt-3">
                            {activeTab === "input" && (
                                <div>
                                    {config?.input_schema ? (
                                        <div>
                                            <label className="mb-2 flex items-center text-sm font-medium text-gray-500 dark:text-gray-400">
                                                <FileJson size={14} className="mr-1" />
                                                Schema
                                            </label>
                                            <div className="max-h-64 overflow-auto rounded-lg border">
                                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                <JSONViewer data={config.input_schema as any} maxDepth={2} className="border-none text-xs" />
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                            No input schema defined
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === "output" && (
                                <div className="space-y-4">
                                    {config?.output_schema ? (
                                        <div>
                                            <label className="mb-2 flex items-center text-sm font-medium text-gray-500 dark:text-gray-400">
                                                <FileJson size={14} className="mr-1" />
                                                Schema
                                            </label>
                                            <div className="max-h-64 overflow-auto rounded-lg border">
                                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                <JSONViewer data={config.output_schema as any} maxDepth={2} className="border-none text-xs" />
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                            No output schema defined
                                        </div>
                                    )}

                                    {/* Output Mapping */}
                                    {config?.output_mapping && (
                                        <div>
                                            <label className="mb-2 flex items-center text-sm font-medium text-gray-500 dark:text-gray-400">
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
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Provider */}
                {workflow.provider && (
                    <div className="border-t pt-4">
                        <label className="mb-2 block text-sm font-medium text-gray-500 dark:text-gray-400">
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
