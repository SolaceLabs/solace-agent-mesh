import React, { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import yaml from "js-yaml";
import {
    X,
    Bot,
    Workflow,
    GitBranch,
    Repeat2,
    RefreshCw,
    Play,
    CheckCircle,
    Copy,
    Check,
    Code,
    ExternalLink,
} from "lucide-react";

import type { LayoutNode } from "./utils/types";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import { getAgentSchemas } from "@/lib/utils/agentUtils";
import type { AgentCardInfo } from "@/lib/types";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui/tabs";
import { Button } from "@/lib/components/ui/button";
import { JSONViewer } from "@/lib/components/jsonViewer";

interface WorkflowNodeDetailPanelProps {
    node: LayoutNode | null;
    workflowConfig: WorkflowConfig | null;
    agents: AgentCardInfo[];
    onClose: () => void;
}

/**
 * WorkflowNodeDetailPanel - Shows details for the selected workflow node
 * Includes input/output schemas, code view toggle, and agent information
 */
const WorkflowNodeDetailPanel: React.FC<WorkflowNodeDetailPanelProps> = ({
    node,
    workflowConfig: _workflowConfig,
    agents,
    onClose,
}) => {
    // workflowConfig is available for future use (e.g., accessing workflow-level output_mapping)
    void _workflowConfig;
    const navigate = useNavigate();
    const [showCodeView, setShowCodeView] = useState(false);
    const [isCopied, setIsCopied] = useState(false);
    const [isNodeIdCopied, setIsNodeIdCopied] = useState(false);
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

    // Handle copy node ID to clipboard
    const handleCopyNodeId = useCallback(() => {
        if (!node?.id) return;
        navigator.clipboard.writeText(node.id);
        setIsNodeIdCopied(true);
        setTimeout(() => setIsNodeIdCopied(false), 2000);
    }, [node?.id]);

    // Handle switching to code view
    const handleInspectCode = useCallback(() => {
        setShowCodeView(true);
    }, []);

    // Handle switching to details view
    const handleShowDetails = useCallback(() => {
        setShowCodeView(false);
    }, []);

    // Navigate to nested workflow
    const handleOpenWorkflow = useCallback(() => {
        if (node?.data.workflowName) {
            navigate(`/agents/workflows/${encodeURIComponent(node.data.workflowName)}`);
        }
    }, [navigate, node?.data.workflowName]);

    if (!node) {
        return null;
    }

    // Get icon based on node type
    const getNodeIcon = () => {
        switch (node.type) {
            case "start":
                return <Play className="h-5 w-5 text-indigo-500" />;
            case "end":
                return <CheckCircle className="h-5 w-5 text-indigo-500" />;
            case "agent":
                return <Bot className="h-5 w-5 text-blue-500" />;
            case "workflow":
                return <Workflow className="h-5 w-5 text-purple-500" />;
            case "switch":
                return <GitBranch className="h-5 w-5 text-purple-500" />;
            case "map":
                return <Repeat2 className="h-5 w-5 text-indigo-500" />;
            case "loop":
                return <RefreshCw className="h-5 w-5 text-teal-500" />;
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

    // Get agent status badge based on last_seen timestamp
    const renderStatusBadge = () => {
        if (!agentInfo) return null;
        // Consider agent online if last_seen within last 60 seconds
        const lastSeen = agentInfo.last_seen ? new Date(agentInfo.last_seen) : null;
        const isOnline = lastSeen ? Date.now() - lastSeen.getTime() < 60000 : false;
        return (
            <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                    isOnline
                        ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                }`}
            >
                <span
                    className={`h-1.5 w-1.5 rounded-full ${isOnline ? "bg-green-500" : "bg-gray-400"}`}
                />
                {isOnline ? "Online" : "Offline"}
            </span>
        );
    };

    // Render YAML code view
    const renderCodeView = () => {
        if (!nodeConfig) return null;
        try {
            const yamlStr = yaml.dump(nodeConfig, { indent: 2, lineWidth: -1 });
            return (
                <pre className="scrollbar-themed overflow-auto rounded-lg bg-gray-100 p-3 font-mono text-xs text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                    {yamlStr}
                </pre>
            );
        } catch {
            return (
                <div className="text-muted-foreground text-sm">Unable to display YAML</div>
            );
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
    const title = node.type === "agent"
        ? (agentDisplayName || node.data.agentName || node.id)
        : (node.data.workflowName || node.id);

    return (
        <div className="flex h-full flex-col bg-white dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    {getNodeIcon()}
                    <span className="font-medium text-gray-900 dark:text-gray-100">{title}</span>
                </div>
                <div className="flex items-center gap-2">
                    {showCodeView ? (
                        <button
                            onClick={handleShowDetails}
                            className="flex items-center gap-1.5 text-sm text-[var(--color-brand-wMain)] hover:underline"
                        >
                            {getNodeIcon()}
                            Show Details
                        </button>
                    ) : (
                        <button
                            onClick={handleInspectCode}
                            className="flex items-center gap-1.5 text-sm text-[var(--color-brand-wMain)] hover:underline"
                        >
                            <Code className="h-4 w-4" />
                            Inspect Code
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
                    renderCodeView()
                ) : (
                    <>
                        {/* Node ID */}
                        <div className="mb-4">
                            <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                Node ID
                            </label>
                            <div className="flex items-center gap-2">
                                <code className="flex-1 rounded bg-gray-100 px-2 py-1 font-mono text-sm text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                                    {node.id}
                                </code>
                                <button
                                    onClick={handleCopyNodeId}
                                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                                    title="Copy node ID"
                                >
                                    {isNodeIdCopied ? (
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4" />
                                    )}
                                </button>
                            </div>
                        </div>

                        {/* Status (for agent nodes) */}
                        {node.type === "agent" && agentInfo && (
                            <div className="mb-4 flex items-center gap-3">
                                <div>
                                    <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                        Status
                                    </label>
                                    {renderStatusBadge()}
                                </div>
                                <div>
                                    <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                        Node Type
                                    </label>
                                    <div className="text-sm text-gray-900 dark:text-gray-100">
                                        {getTypeLabel()}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Node Type (for non-agent nodes) */}
                        {node.type !== "agent" && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Node Type
                                </label>
                                <div className="text-sm text-gray-900 dark:text-gray-100">
                                    {getTypeLabel()}
                                </div>
                            </div>
                        )}

                        {/* Description (from agent card) */}
                        {agentDescription && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Description
                                </label>
                                <div className="text-sm text-gray-700 dark:text-gray-300">
                                    {agentDescription}
                                </div>
                            </div>
                        )}

                        {/* Instruction (for agent nodes) */}
                        {nodeConfig?.instruction && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Instruction
                                </label>
                                <div className="rounded bg-gray-100 p-2 text-sm text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                                    {nodeConfig.instruction}
                                </div>
                            </div>
                        )}

                        {/* Open Workflow button (for workflow ref nodes) */}
                        {node.type === "workflow" && node.data.workflowName && (
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

                        {/* Condition (for loop nodes) */}
                        {node.data.condition && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Condition
                                </label>
                                <div className="rounded bg-gray-100 p-2 font-mono text-xs text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                                    {node.data.condition}
                                </div>
                            </div>
                        )}

                        {/* Max Iterations (for loop nodes) */}
                        {node.data.maxIterations && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Max Iterations
                                </label>
                                <div className="text-sm text-gray-900 dark:text-gray-100">
                                    {node.data.maxIterations}
                                </div>
                            </div>
                        )}

                        {/* Cases (for switch nodes) */}
                        {node.data.cases && node.data.cases.length > 0 && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Cases
                                </label>
                                <div className="space-y-2">
                                    {node.data.cases.map((caseItem, index) => (
                                        <div
                                            key={index}
                                            className="rounded bg-gray-100 p-2 dark:bg-gray-700"
                                        >
                                            <div className="mb-1 text-xs font-medium text-gray-600 dark:text-gray-400">
                                                Case {index + 1}
                                            </div>
                                            <div className="font-mono text-xs text-gray-800 dark:text-gray-200">
                                                {caseItem.condition}
                                            </div>
                                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                                                → {caseItem.node}
                                            </div>
                                        </div>
                                    ))}
                                    {node.data.defaultCase && (
                                        <div className="rounded bg-gray-100 p-2 dark:bg-gray-700">
                                            <div className="mb-1 text-xs font-medium text-gray-600 dark:text-gray-400">
                                                Default
                                            </div>
                                            <div className="text-xs text-gray-800 dark:text-gray-200">
                                                → {node.data.defaultCase}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Items (for map nodes) */}
                        {node.data.items && (
                            <div className="mb-4">
                                <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                    Items
                                </label>
                                <div className="rounded bg-gray-100 p-2 font-mono text-xs text-gray-800 dark:bg-gray-700 dark:text-gray-200">
                                    {node.data.items}
                                </div>
                            </div>
                        )}

                        {/* Input/Output Tabs (for agent and workflow nodes) */}
                        {hasSchemas && (
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

                                    <TabsContent value="input" className="mt-0 space-y-4">
                                        {hasInputData ? (
                                            <>
                                                {/* Input Mapping */}
                                                {getInputMapping() && (
                                                    <div>
                                                        <label className="mb-2 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                                            Mapping
                                                        </label>
                                                        <div className="max-h-48 overflow-auto rounded-lg border">
                                                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                            <JSONViewer
                                                                data={getInputMapping() as any}
                                                                maxDepth={3}
                                                                className="border-none text-xs"
                                                            />
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Input Schema */}
                                                {getInputSchema() && (
                                                    <div>
                                                        <label className="mb-2 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                                            Schema
                                                            {isInputSchemaFromAgent && (
                                                                <span className="ml-2 font-normal text-gray-400 dark:text-gray-500">
                                                                    (from agent)
                                                                </span>
                                                            )}
                                                        </label>
                                                        <div className="max-h-48 overflow-auto rounded-lg border">
                                                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                            <JSONViewer
                                                                data={getInputSchema() as any}
                                                                maxDepth={3}
                                                                className="border-none text-xs"
                                                            />
                                                        </div>
                                                    </div>
                                                )}
                                            </>
                                        ) : (
                                            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                                No input defined
                                            </div>
                                        )}
                                    </TabsContent>

                                    <TabsContent value="output" className="mt-0">
                                        {getOutputSchema() ? (
                                            <div>
                                                <label className="mb-2 block text-xs font-medium text-gray-500 dark:text-gray-400">
                                                    Schema
                                                    {isOutputSchemaFromAgent && (
                                                        <span className="ml-2 font-normal text-gray-400 dark:text-gray-500">
                                                            (from agent)
                                                        </span>
                                                    )}
                                                </label>
                                                <div className="max-h-64 overflow-auto rounded-lg border">
                                                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                                    <JSONViewer
                                                        data={getOutputSchema() as any}
                                                        maxDepth={3}
                                                        className="border-none text-xs"
                                                    />
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                                                No output schema defined
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

export default WorkflowNodeDetailPanel;
