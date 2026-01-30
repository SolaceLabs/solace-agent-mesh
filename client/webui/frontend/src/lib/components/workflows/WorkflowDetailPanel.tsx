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

export const WorkflowDetailPanel: React.FC<WorkflowDetailPanelProps> = ({ workflow, config: providedConfig, onClose, showOpenButton = true }) => {
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
        if (descriptionRef.current && description) {
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
        <div className="flex h-full flex-col border-l">
            {/* Header */}
            <div className="flex items-center justify-between gap-2 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex min-w-0 items-center gap-2">
                    <Workflow className="h-5 w-5 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <span className="truncate text-xl font-semibold">{workflow.displayName || workflow.name}</span>
                        </TooltipTrigger>
                        <TooltipContent>{workflow.displayName || workflow.name}</TooltipContent>
                    </Tooltip>
                </div>
                <div className="flex items-center gap-2">
                    {/* View toggle */}
                    <div className="flex overflow-hidden rounded-md border">
                        <button onClick={() => setShowCodeView(false)} className={`flex items-center justify-center px-3 py-1.5 ${!showCodeView ? "bg-[var(--color-brand-wMain)]/10" : "bg-background hover:bg-muted"}`} title="Details view">
                            <FileText className="h-4 w-4" />
                        </button>
                        <button onClick={() => setShowCodeView(true)} className={`flex items-center justify-center border-l px-3 py-1.5 ${showCodeView ? "bg-[var(--color-brand-wMain)]/10" : "bg-background hover:bg-muted"}`} title="Code view">
                            <Code className="h-4 w-4" />
                        </button>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} tooltip="Close">
                        <X className="h-5 w-5" />
                    </Button>
                </div>
            </div>

            {/* Toolbar (only for code view) */}
            {showCodeView && (
                <div className="flex items-center justify-end gap-1 border-b px-3 py-2">
                    <Button onClick={handleCopy} tooltip="Copy YAML" variant="ghost">
                        {isCopied ? <Check className="h-4 w-4 text-[var(--color-brand-wMain)]" /> : <Copy className="h-4 w-4" />}
                    </Button>
                </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
                {showCodeView ? (
                    // Code view - show YAML
                    config ? (
                        <pre className="bg-muted h-full overflow-auto rounded-sm p-3 font-mono text-xs">{yaml.dump(config, { indent: 2, lineWidth: -1 })}</pre>
                    ) : (
                        <div className="text-muted-foreground text-sm">No configuration available</div>
                    )
                ) : (
                    <>
                        {/* Workflow Details Section */}
                        <div className="bg-muted mb-4 flex flex-col gap-2 rounded-sm p-4">
                            <div className="text-base font-semibold">Workflow Details</div>
                            {/* Description without label */}
                            {description && (
                                <>
                                    <div ref={descriptionRef} className={`prose prose-sm dark:prose-invert max-w-none text-sm ${!isDescriptionExpanded && showExpandButton ? "line-clamp-5" : ""}`}>
                                        <MarkdownHTMLConverter>{description}</MarkdownHTMLConverter>
                                    </div>
                                    {showExpandButton && (
                                        <button onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)} className="flex items-center gap-1 text-sm text-[var(--color-brand-wMain)] hover:underline">
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
                                </>
                            )}
                            {!description && <div className="text-muted-foreground">No description available</div>}
                            {/* Version and Node Count in grid */}
                            <div className="grid grid-cols-2 gap-4 pt-2">
                                <div>
                                    <div className="text-muted-foreground mb-1 text-sm font-medium">Version</div>
                                    <div className="flex items-center gap-1 text-sm">
                                        <GitMerge size={14} className="text-muted-foreground" />
                                        {workflow.version || "N/A"}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-muted-foreground mb-1 text-sm font-medium">Nodes</div>
                                    <div className="flex items-center gap-1 text-sm">
                                        <Workflow size={14} className="text-muted-foreground" />
                                        {nodeCount > 0 ? nodeCount : "N/A"}
                                    </div>
                                </div>
                            </div>
                            {/* Open Workflow button inside details box */}
                            {showOpenButton && (
                                <Button variant="outline" size="sm" onClick={handleOpenWorkflow} className="mt-2 w-full">
                                    <ExternalLink />
                                    Open Workflow
                                </Button>
                            )}
                        </div>

                        {/* Input Schema */}
                        {config?.input_schema && (
                            <div className="mb-4">
                                <label className="text-muted-foreground mb-2 flex items-center text-xs font-medium">
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
                                <label className="text-muted-foreground mb-2 flex items-center text-xs font-medium">
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
                                <label className="text-muted-foreground mb-1 flex items-center text-xs font-medium">
                                    <FileJson size={14} className="mr-1" />
                                    Output Mapping
                                </label>
                                <div className="text-muted-foreground mb-2 text-xs">Defines how the final agent output is mapped to the workflow output schema.</div>
                                <div className="max-h-48 overflow-auto rounded-lg border">
                                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                    <JSONViewer data={config.output_mapping as any} maxDepth={2} className="border-none text-xs" />
                                </div>
                            </div>
                        )}

                        {/* Provider */}
                        {workflow.provider && (
                            <div className="border-t pt-4">
                                <label className="text-muted-foreground mb-2 block text-xs font-medium">Provider</label>
                                <div className="space-y-2 text-sm">
                                    {workflow.provider.organization && (
                                        <div>
                                            <span className="text-muted-foreground">Organization:</span> {workflow.provider.organization}
                                        </div>
                                    )}
                                    {workflow.provider.url && (
                                        <div>
                                            <span className="text-muted-foreground">URL:</span>{" "}
                                            <a href={workflow.provider.url} target="_blank" rel="noopener noreferrer" className="text-[var(--color-brand-wMain)] hover:underline">
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
