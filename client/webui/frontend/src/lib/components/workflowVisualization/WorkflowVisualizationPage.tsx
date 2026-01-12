import React, { useMemo, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Workflow } from "lucide-react";

import { Button, EmptyState } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";
import { isWorkflowAgent, getWorkflowConfig } from "@/lib/utils/agentUtils";
import type { LayoutNode } from "./utils/types";
import WorkflowDiagram from "./WorkflowDiagram";
import WorkflowNodeDetailPanel from "./WorkflowNodeDetailPanel";

/**
 * WorkflowVisualizationPage - Main page for viewing workflow node diagrams
 * Accessible via /agents/workflows/:workflowName
 */
export function WorkflowVisualizationPage() {
    const { workflowName } = useParams<{ workflowName: string }>();
    const navigate = useNavigate();
    const { agents, agentsLoading, agentsError } = useChatContext();

    const [selectedNode, setSelectedNode] = useState<LayoutNode | null>(null);

    // Find the workflow and extract config
    const { workflow, config, knownWorkflows } = useMemo(() => {
        const workflowAgents = agents.filter(isWorkflowAgent);
        const foundWorkflow = workflowAgents.find(
            agent => agent.name === workflowName || agent.displayName === workflowName
        );
        const workflowConfig = foundWorkflow ? getWorkflowConfig(foundWorkflow) : null;

        // Build set of known workflow names for detecting nested workflow references
        const knownWorkflowNames = new Set(workflowAgents.map(w => w.name));

        return {
            workflow: foundWorkflow,
            config: workflowConfig,
            knownWorkflows: knownWorkflowNames,
        };
    }, [agents, workflowName]);

    // Handle node selection
    const handleNodeSelect = useCallback((node: LayoutNode | null) => {
        setSelectedNode(node);
    }, []);

    // Handle detail panel close
    const handleCloseDetail = useCallback(() => {
        setSelectedNode(null);
    }, []);

    // Handle back navigation - return to workflows tab
    const handleBack = useCallback(() => {
        navigate("/agents?tab=workflows");
    }, [navigate]);

    // Calculate side panel width for layout
    const sidePanelWidth = selectedNode ? 320 : 0;

    // Loading state
    if (agentsLoading) {
        return (
            <div className="flex h-full w-full flex-col">
                <PageHeader workflowName={workflowName || "Workflow"} onBack={handleBack} />
                <EmptyState title="Loading..." variant="loading" />
            </div>
        );
    }

    // Error state
    if (agentsError) {
        return (
            <div className="flex h-full w-full flex-col">
                <PageHeader workflowName={workflowName || "Workflow"} onBack={handleBack} />
                <EmptyState variant="error" title="Error loading data" subtitle={agentsError} />
            </div>
        );
    }

    // Workflow not found
    if (!workflow || !config) {
        return (
            <div className="flex h-full w-full flex-col">
                <PageHeader workflowName={workflowName || "Workflow"} onBack={handleBack} />
                <EmptyState
                    variant="error"
                    title="Workflow not found"
                    subtitle={`Could not find a workflow named "${workflowName}"`}
                />
            </div>
        );
    }

    return (
        <div className="flex h-full w-full flex-col">
            <PageHeader
                workflowName={workflow.displayName || workflow.name}
                workflowVersion={config.version}
                onBack={handleBack}
            />

            <div className="relative flex flex-1 overflow-hidden">
                {/* Diagram area */}
                <div className="flex-1">
                    <WorkflowDiagram
                        config={config}
                        knownWorkflows={knownWorkflows}
                        sidePanelWidth={sidePanelWidth}
                        onNodeSelect={handleNodeSelect}
                    />
                </div>

                {/* Detail panel (shown when node selected) */}
                {selectedNode && <WorkflowNodeDetailPanel node={selectedNode} onClose={handleCloseDetail} />}
            </div>
        </div>
    );
}

/**
 * Page header component
 */
interface PageHeaderProps {
    workflowName: string;
    workflowVersion?: string;
    onBack: () => void;
}

const PageHeader: React.FC<PageHeaderProps> = ({ workflowName, workflowVersion, onBack }) => {
    return (
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={onBack}>
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <div className="flex items-center gap-2">
                    <Workflow className="h-5 w-5 text-[var(--color-brand-wMain)]" />
                    <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{workflowName}</h1>
                    {workflowVersion && (
                        <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-700 dark:text-gray-400">
                            v{workflowVersion}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
};

export default WorkflowVisualizationPage;
