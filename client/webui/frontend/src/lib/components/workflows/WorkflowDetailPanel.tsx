import React from "react";

import type { AgentCardInfo } from "@/lib/types";
import { getWorkflowConfig, getWorkflowNodeCount } from "@/lib/utils/agentUtils";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/lib/components/ui/sheet";
import { Button } from "@/lib/components/ui/button";
import { MarkdownHTMLConverter } from "@/lib/components/common";
import { JSONViewer } from "@/lib/components/jsonViewer";
import { Workflow, GitMerge, Box, FileJson } from "lucide-react";

interface WorkflowDetailPanelProps {
    workflow: AgentCardInfo | null;
    onClose: () => void;
}

interface DetailItemProps {
    label: string;
    value: React.ReactNode;
    icon?: React.ReactNode;
}

const DetailItem: React.FC<DetailItemProps> = ({ label, value, icon }) => {
    if (value === undefined || value === null || value === "") return null;
    return (
        <div className="mb-4">
            <div className="text-muted-foreground mb-2 flex items-center text-xs font-semibold uppercase tracking-wide">
                {icon && <span className="mr-2">{icon}</span>}
                {label}
            </div>
            <div className="text-sm">{value}</div>
        </div>
    );
};

export const WorkflowDetailPanel: React.FC<WorkflowDetailPanelProps> = ({ workflow, onClose }) => {
    if (!workflow) {
        return null;
    }

    const config = getWorkflowConfig(workflow);
    const nodeCount = getWorkflowNodeCount(workflow);
    const description = config?.description || workflow.description;

    const handleOpenWorkflow = () => {
        // Placeholder - functionality in future story
        console.log("Open workflow:", workflow.name);
    };

    return (
        <Sheet open={!!workflow} onOpenChange={open => !open && onClose()}>
            <SheetContent side="right" className="flex w-[480px] flex-col p-0 sm:max-w-[480px]">
                <SheetHeader className="border-b px-6 py-5">
                    <SheetTitle className="flex items-center gap-3 text-lg">
                        <Workflow className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                        <span className="truncate">{workflow.displayName || workflow.name}</span>
                    </SheetTitle>
                </SheetHeader>

                <div className="scrollbar-themed flex-1 space-y-6 overflow-y-auto px-6 py-6">
                    {description && (
                        <div className="mb-6">
                            <div className="text-muted-foreground mb-2 text-xs font-semibold uppercase tracking-wide">Description</div>
                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                <MarkdownHTMLConverter>{description}</MarkdownHTMLConverter>
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <DetailItem label="Version" value={workflow.version || "N/A"} icon={<GitMerge size={14} />} />
                        <DetailItem label="Nodes" value={nodeCount > 0 ? `${nodeCount} nodes` : "N/A"} icon={<Workflow size={14} />} />
                    </div>

                    {config?.input_schema && (
                        <div className="mb-4">
                            <div className="text-muted-foreground mb-2 flex items-center text-xs font-semibold uppercase tracking-wide">
                                <FileJson size={14} className="mr-2" />
                                Input Schema
                            </div>
                            <div className="max-h-48 overflow-auto rounded-lg border">
                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                <JSONViewer data={config.input_schema as any} maxDepth={2} className="border-none text-xs" />
                            </div>
                        </div>
                    )}

                    {config?.output_schema && (
                        <div className="mb-4">
                            <div className="text-muted-foreground mb-2 flex items-center text-xs font-semibold uppercase tracking-wide">
                                <Box size={14} className="mr-2" />
                                Output Schema
                            </div>
                            <div className="max-h-48 overflow-auto rounded-lg border">
                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                <JSONViewer data={config.output_schema as any} maxDepth={2} className="border-none text-xs" />
                            </div>
                        </div>
                    )}

                    {workflow.provider && (
                        <div className="border-t pt-4">
                            <div className="text-muted-foreground mb-3 text-xs font-semibold uppercase tracking-wide">Provider</div>
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
                </div>

                <SheetFooter className="border-t px-6 py-4">
                    <Button onClick={handleOpenWorkflow} className="w-full" variant="outline">
                        Open Workflow
                    </Button>
                </SheetFooter>
            </SheetContent>
        </Sheet>
    );
};
