import { useState, useEffect, useRef } from "react";
import { Workflow, GitMerge, FileJson, X, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig, getWorkflowNodeCount } from "@/lib/utils/agentUtils";
import { Button, JSONViewer, MarkdownHTMLConverter } from "@/lib/components";

interface WorkflowDetailPanelProps {
    workflow: AgentCardInfo;
    /** Optional config - if not provided, will be computed from workflow */
    config?: ReturnType<typeof getWorkflowConfig>;
    onClose: () => void;
    /** Whether to show the "Open Workflow" button (default: true) */
    showOpenButton?: boolean;
}

export const WorkflowDetailPanel = ({ workflow, config: providedConfig, onClose, showOpenButton = true }: WorkflowDetailPanelProps) => {
    const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false);
    const [showExpandButton, setShowExpandButton] = useState(false);
    const descriptionRef = useRef<HTMLDivElement>(null);

    const config = providedConfig ?? getWorkflowConfig(workflow);
    const nodeCount = getWorkflowNodeCount(workflow);
    const description = config?.description || workflow.description;

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
        window.open(`/#/agents/workflows/${encodeURIComponent(workflow.name)}`, "_blank");
    };

    return (
        <div className="flex h-full flex-col border-l">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
                <div className="flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-[var(--color-brand-wMain)]" />
                    <span className="font-medium">{workflow.displayName || workflow.name}</span>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" onClick={onClose}>
                        <X />
                    </Button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
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
                                    <Button onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)} variant="ghost" className="w-fit">
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
            </div>
        </div>
    );
};
