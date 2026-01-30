import React, { useState, useCallback, useMemo } from "react";
import yaml from "js-yaml";
import { Bot, Workflow, GitBranch, Repeat2, RefreshCw, Play, CheckCircle, Copy, Check, Code, ExternalLink, FileText } from "lucide-react";

import type { LayoutNode } from "./utils/types";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import { getAgentSchemas } from "@/lib/utils/agentUtils";
import type { AgentCardInfo } from "@/lib/types";
import { Button } from "@/lib/components/ui/button";
import { JSONViewer, type JSONValue } from "@/lib/components/jsonViewer";
import InputMappingViewer from "./InputMappingViewer";
import { buildWorkflowNavigationUrl } from "./WorkflowVisualizationPage";

interface WorkflowNodeDetailPanelProps {
    node: LayoutNode | null;
    workflowConfig: WorkflowConfig | null;
    agents: AgentCardInfo[];
    /** Callback to highlight nodes when hovering over expressions */
    onHighlightNodes?: (nodeIds: string[]) => void;
    /** Set of known node IDs for validating expression references */
    knownNodeIds?: Set<string>;
    /** Callback to navigate/pan to a node when clicking the navigation icon */
    onNavigateToNode?: (nodeId: string) => void;
    /** Current workflow name - used for building sub-workflow navigation URLs */
    currentWorkflowName?: string;
    /** Parent workflow path (for breadcrumb navigation) */
    parentPath?: string[];
}

/**
 * WorkflowNodeDetailPanel - Shows details for the selected workflow node
 * Includes input/output schemas, code view toggle, and agent information
 */
const WorkflowNodeDetailPanel: React.FC<WorkflowNodeDetailPanelProps> = ({ node, workflowConfig: _workflowConfig, agents, onHighlightNodes, knownNodeIds, onNavigateToNode, currentWorkflowName, parentPath = [] }) => {
    // workflowConfig is available for future use (e.g., accessing workflow-level output_mapping)
    void _workflowConfig;
    const [showCodeView, setShowCodeView] = useState(false);
    const [isCopied, setIsCopied] = useState(false);
    const [activeTab, setActiveTab] = useState<"input" | "output">("input");

    // Look up agent info for agent nodes
    const agentInfo = useMemo(() => {
        if (!node?.data.agentName) return null;
        return agents.find(a => a.name === node.data.agentName) || null;
    }, [node?.data.agentName, agents]);

    // Extract schemas from agent card (used as fallback when no overrides)
    const agentSchemas = useMemo(() => {
        if (!agentInfo) return { inputSchema: undefined, outputSchema: undefined };
        return getAgentSchemas(agentInfo);
    }, [agentInfo]);

    // Get the original node config
    const nodeConfig = node?.data.originalConfig;

    // Handle copy to clipboard
    const handleCopy = useCallback(() => {
        if (!nodeConfig) return;
        try {
            const yamlStr = yaml.dump(nodeConfig, { indent: 2, lineWidth: -1 });
            navigator.clipboard.writeText(yamlStr);
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    }, [nodeConfig]);

    // Handle switching to code view
    const handleInspectCode = useCallback(() => {
        setShowCodeView(true);
    }, []);

    // Handle switching to details view
    const handleShowDetails = useCallback(() => {
        setShowCodeView(false);
    }, []);

    // Navigate to nested workflow with parent path tracking for breadcrumbs
    const handleOpenWorkflow = useCallback(() => {
        if (node?.data.workflowName) {
            // Build new parent path: current workflow becomes closest parent
            const newParentPath = currentWorkflowName ? [currentWorkflowName, ...parentPath] : parentPath;
            window.open("/#" + buildWorkflowNavigationUrl(node.data.workflowName, newParentPath), "_blank");
        }
    }, [node?.data.workflowName, currentWorkflowName, parentPath]);

    if (!node) {
        return null;
    }

    // Get icon based on node type
    const getNodeIcon = () => {
        switch (node.type) {
            case "start":
                return <Play className="h-6 w-6" />;
            case "end":
                return <CheckCircle className="h-6 w-6" />;
            case "agent":
                return <Bot className="h-6 w-6 text-(--color-brand-wMain)" />;
            case "workflow":
                return <Workflow className="h-6 w-6 text-(--color-brand-wMain)" />;
            case "switch":
                return <GitBranch className="h-6 w-6 text-(--color-accent-n0-wMain)" />;
            case "map":
                return <Repeat2 className="h-6 w-6 text-(--color-accent-n0-wMain)" />;
            case "loop":
                return <RefreshCw className="h-6 w-6 text-(--color-accent-n0-wMain)" />;
            default:
                return null;
        }
    };

    // Get type label
    const getTypeLabel = () => {
        switch (node.type) {
            case "start":
                return "Start Node";
            case "end":
                return "End Node";
            case "agent":
                return "Agent";
            case "workflow":
                return "Workflow";
            case "switch":
                return "Switch";
            case "map":
                return "Map";
            case "loop":
                return "Loop";
            default:
                return "Node";
        }
    };

    // Get agent status badge - consider online if we have agent info (agent responded to discovery)
    const renderStatusBadge = () => {
        // If we have agent info, the agent is online (it responded to discovery)
        const isOnline = !!agentInfo;
        return (
            <span className="inline-flex items-center gap-1 text-sm font-medium">
                <span className={`h-1.5 w-1.5 rounded-full ${isOnline ? "bg-green-500" : "bg-gray-400"}`} />
                {isOnline ? "Running" : "Offline"}
            </span>
        );
    };

    // Render YAML code view
    const renderCodeView = () => {
        if (!nodeConfig) {
            return <div className="bg-card-background flex h-full items-center justify-center">There is no code associated with this node.</div>;
        }
        try {
            const yamlStr = yaml.dump(nodeConfig, { indent: 2, lineWidth: -1 });
            return (
                <div className="relative h-full">
                    <Button variant="ghost" size="icon" onClick={handleCopy} tooltip={isCopied ? "Copied!" : "Copy"} className="absolute top-2 right-2 z-10 h-8 w-8">
                        {isCopied ? <Check className="h-4 w-4 text-(--color-success-wMain)" /> : <Copy className="h-4 w-4" />}
                    </Button>
                    <pre className="scrollbar-themed bg-card-background h-full overflow-auto rounded-lg p-3 font-mono text-sm dark:border">{yamlStr}</pre>
                </div>
            );
        } catch {
            return <div className="text-muted-foreground text-sm">Unable to display YAML</div>;
        }
    };

    // Check if node has schemas to show tabs
    const hasSchemas = node.type === "agent" || node.type === "workflow";

    // Get input mapping (how fields are mapped into the agent)
    const getInputMapping = () => {
        return nodeConfig?.input || null;
    };

    // Get input schema (node override takes precedence, then agent card schema)
    const getInputSchema = () => {
        return nodeConfig?.input_schema_override || agentSchemas.inputSchema || null;
    };

    // Get output schema (node override takes precedence, then agent card schema)
    const getOutputSchema = () => {
        return nodeConfig?.output_schema_override || agentSchemas.outputSchema || null;
    };

    // Check if the schema shown is from the agent card (not a node override)
    const isInputSchemaFromAgent = !nodeConfig?.input_schema_override && !!agentSchemas.inputSchema;
    const isOutputSchemaFromAgent = !nodeConfig?.output_schema_override && !!agentSchemas.outputSchema;

    // Check if input tab has any data
    const hasInputData = getInputMapping() || getInputSchema();

    // Get agent display name (prefer displayName, fall back to display_name, then name)
    const agentDisplayName = agentInfo?.displayName || agentInfo?.display_name || agentInfo?.name;

    // Get agent description from agent card
    const agentDescription = agentInfo?.description;

    // Get the title (always show node name, regardless of view mode)
    const title = node.type === "agent" ? agentDisplayName || node.data.agentName || node.id : node.data.workflowName || node.id;

    return (
        <div className="bg-background flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b p-4">
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                    {getNodeIcon()}
                    <span className="truncate pr-2 text-[20px] font-semibold" title={title}>
                        {title}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    {/* View toggle */}
                    <div className="flex overflow-hidden rounded-md border">
                        <button
                            onClick={handleShowDetails}
                            className={`flex items-center justify-center px-3 py-1.5 ${
                                !showCodeView ? "bg-(--color-brand-wMain)/10 text-gray-700 dark:text-gray-200" : "bg-white text-gray-500 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                            }`}
                            title="Details view"
                        >
                            <FileText className="h-4 w-4" />
                        </button>
                        <button
                            onClick={handleInspectCode}
                            className={`flex items-center justify-center border-l border-gray-300 px-3 py-1.5 dark:border-gray-600 ${
                                showCodeView ? "bg-(--color-brand-wMain)/10 text-gray-700 dark:text-gray-200" : "bg-white text-gray-500 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                            }`}
                            title="Code view"
                        >
                            <Code className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="scrollbar-themed flex-1 overflow-auto">
                {showCodeView ? (
                    <div className="h-full p-4">{renderCodeView()}</div>
                ) : (
                    <div className="p-4">
                        {/* Node ID */}
                        <div className="mb-4">
                            <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Node ID</label>
                            <code className="font-mono text-sm">{node.id}</code>
                        </div>

                        {/* Status (for agent nodes) */}
                        {node.type === "agent" && (
                            <div className="mb-4 grid grid-cols-2 gap-4">
                                <div>
                                    <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Status</label>
                                    {renderStatusBadge()}
                                </div>
                                <div>
                                    <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Node Type</label>
                                    <div className="text-sm">{getTypeLabel()}</div>
                                </div>
                            </div>
                        )}

                        {/* Node Type (for non-agent nodes) */}
                        {node.type !== "agent" && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Node Type</label>
                                <div className="text-sm">{getTypeLabel()}</div>
                            </div>
                        )}

                        {/* Description (from agent card) */}
                        {agentDescription && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Description</label>
                                <div className="text-sm">{agentDescription}</div>
                            </div>
                        )}

                        {/* Instruction (for agent nodes) */}
                        {nodeConfig?.instruction && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Instruction</label>
                                <div className="text-sm">{nodeConfig.instruction}</div>
                            </div>
                        )}

                        {/* Open Workflow button (for workflow ref nodes) */}
                        {node.type === "workflow" && node.data.workflowName && (
                            <div className="mb-4">
                                <Button variant="outline" size="sm" onClick={handleOpenWorkflow} className="w-full">
                                    Open Workflow
                                    <ExternalLink className="ml-2 h-4 w-4" />
                                </Button>
                            </div>
                        )}

                        {/* Max Iterations (for loop nodes) */}
                        {node.data.maxIterations && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Max Iterations</label>
                                <div className="text-sm">{node.data.maxIterations}</div>
                            </div>
                        )}

                        {/* Condition (for loop nodes) */}
                        {node.data.condition && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Condition</label>
                                <div className="rounded bg-gray-100 p-2 font-mono text-xs dark:bg-gray-700">{node.data.condition}</div>
                            </div>
                        )}

                        {/* Cases (for switch nodes) */}
                        {node.data.cases && node.data.cases.length > 0 && (
                            <div className="mb-4">
                                <label className="mb-2 block text-sm font-normal text-(--color-secondary-text-wMain)">Cases</label>
                                <div className="space-y-2">
                                    {node.data.cases.map((caseItem, index) => (
                                        <div key={index} className="grid grid-cols-[auto_1fr] gap-3">
                                            <div className="flex h-8 w-[30px] items-center justify-center rounded border border-(--color-secondary-w20) bg-(--color-background-w10) text-sm text-(--color-secondary-text-wMain)">{index + 1}</div>
                                            <div className="mb-2">
                                                <div className="mb-1 min-h-[32px] bg-(--color-background-w20) p-2 font-mono text-xs">{caseItem.condition}</div>
                                                <div className="text-sm">→ {caseItem.node}</div>
                                            </div>
                                        </div>
                                    ))}
                                    {node.data.defaultCase && (
                                        <div className="grid grid-cols-[auto_1fr] gap-3">
                                            <div className="flex h-8 w-[30px] items-center justify-center rounded border border-(--color-secondary-w20) bg-(--color-background-w10) text-sm text-(--color-secondary-text-wMain)">
                                                {node.data.cases.length + 1}
                                            </div>
                                            <div className="flex min-h-[32px] items-center bg-(--color-background-w20) p-2">
                                                <span className="text-sm">default</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Items (for map nodes) */}
                        {node.data.items && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Items</label>
                                <div className="rounded bg-gray-100 p-2 font-mono text-xs dark:bg-gray-700">{node.data.items}</div>
                            </div>
                        )}

                        {/* Input/Output Tabs (for agent and workflow nodes) */}
                        {hasSchemas && (
                            <div className="mt-8">
                                {/* Tab Headers */}
                                <div className="mb-4 flex border-b border-gray-200 dark:border-gray-700" role="tablist">
                                    <button
                                        role="tab"
                                        aria-selected={activeTab === "input"}
                                        onClick={() => setActiveTab("input")}
                                        className={`px-4 pb-2 font-medium transition-colors ${
                                            activeTab === "input" ? "border-b-2 border-(--color-brand-wMain) font-semibold text-gray-900 dark:text-gray-100" : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                                        }`}
                                    >
                                        Input
                                    </button>
                                    <button
                                        role="tab"
                                        aria-selected={activeTab === "output"}
                                        onClick={() => setActiveTab("output")}
                                        className={`ml-6 px-4 pb-2 font-medium transition-colors ${
                                            activeTab === "output" ? "border-b-2 border-(--color-brand-wMain) font-semibold text-gray-900 dark:text-gray-100" : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                                        }`}
                                    >
                                        Output
                                    </button>
                                </div>

                                {/* Tab Content */}
                                {activeTab === "input" && (
                                    <div className="space-y-4">
                                        {hasInputData ? (
                                            <>
                                                {/* Input Mapping */}
                                                {getInputMapping() && (
                                                    <div>
                                                        <label className="mb-4 block text-sm font-medium text-(--color-secondary-text-wMain)">Mapping</label>
                                                        <InputMappingViewer mapping={getInputMapping() as Record<string, unknown>} onHighlightNodes={onHighlightNodes} knownNodeIds={knownNodeIds} onNavigateToNode={onNavigateToNode} />
                                                    </div>
                                                )}

                                                {/* Input Schema */}
                                                {getInputSchema() && (
                                                    <div>
                                                        <label className="mb-2 block text-sm font-medium text-(--color-secondary-text-wMain)">
                                                            Schema
                                                            {isInputSchemaFromAgent && <span className="ml-2 font-normal text-gray-400 dark:text-gray-500">(from agent)</span>}
                                                        </label>
                                                        <div className="max-h-48 overflow-auto rounded-lg border">
                                                            <JSONViewer data={getInputSchema() as JSONValue} maxDepth={3} className="border-none text-xs" />
                                                        </div>
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">No input defined</div>
                                        )}
                                    </div>
                                )}

                                {activeTab === "output" && (
                                    <div>
                                        {getOutputSchema() ? (
                                            <div>
                                                <label className="mb-2 block text-sm font-medium text-(--color-secondary-text-wMain)">
                                                    Schema
                                                    {isOutputSchemaFromAgent && <span className="ml-2 font-normal text-gray-400 dark:text-gray-500">(from agent)</span>}
                                                </label>
                                                <div className="max-h-64 overflow-auto rounded-lg border">
                                                    <JSONViewer data={getOutputSchema() as JSONValue} maxDepth={3} className="border-none text-xs" />
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">No output schema defined</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default WorkflowNodeDetailPanel;
