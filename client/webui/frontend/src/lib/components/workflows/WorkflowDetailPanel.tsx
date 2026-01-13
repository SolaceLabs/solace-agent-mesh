import React from "react";
import { useNavigate } from "react-router-dom";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig, getWorkflowNodeCount } from "@/lib/utils/agentUtils";
import { Button } from "@/lib/components/ui/button";
import { MarkdownHTMLConverter } from "@/lib/components/common";
import { JSONViewer } from "@/lib/components/jsonViewer";
import { Workflow, GitMerge, FileJson, X, ExternalLink } from "lucide-react";

interface WorkflowDetailPanelProps {
    workflow: AgentCardInfo;
    onClose: () => void;
}

export const WorkflowDetailPanel: React.FC<WorkflowDetailPanelProps> = ({ workflow, onClose }) => {
    const navigate = useNavigate();

    const config = getWorkflowConfig(workflow);
    const nodeCount = getWorkflowNodeCount(workflow);
    const description = config?.description || workflow.description;

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
                <button
                    onClick={onClose}
                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                >
                    <X className="h-5 w-5" />
                </button>
            </div>

            {/* Content */}
            <div className="scrollbar-themed flex-1 overflow-y-auto p-4">
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
                        <div className="prose prose-sm dark:prose-invert max-w-none text-sm text-gray-700 dark:text-gray-300">
                            <MarkdownHTMLConverter>{description}</MarkdownHTMLConverter>
                        </div>
                    </div>
                )}

                {/* Open Workflow button */}
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
            </div>
        </div>
    );
};
