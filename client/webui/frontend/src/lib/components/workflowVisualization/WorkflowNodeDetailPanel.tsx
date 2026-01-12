import React from "react";
import { X, Bot, Workflow, GitBranch, Repeat2, RefreshCw, Play, CheckCircle } from "lucide-react";
import type { LayoutNode } from "./utils/types";

interface WorkflowNodeDetailPanelProps {
    node: LayoutNode | null;
    onClose: () => void;
}

/**
 * WorkflowNodeDetailPanel - Placeholder panel showing selected node details
 * Will be expanded in a future story
 */
const WorkflowNodeDetailPanel: React.FC<WorkflowNodeDetailPanelProps> = ({ node, onClose }) => {
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
                return "Agent Node";
            case "workflow":
                return "Workflow Reference";
            case "switch":
                return "Switch Node";
            case "map":
                return "Map Node";
            case "loop":
                return "Loop Node";
            default:
                return "Node";
        }
    };

    return (
        <div className="flex h-full w-80 flex-col border-l border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <div className="flex items-center gap-2">
                    {getNodeIcon()}
                    <span className="font-medium text-gray-900 dark:text-gray-100">{getTypeLabel()}</span>
                </div>
                <button
                    onClick={onClose}
                    className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                >
                    <X className="h-5 w-5" />
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
                {/* Node ID */}
                <div className="mb-4">
                    <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Node ID</label>
                    <div className="text-sm text-gray-900 dark:text-gray-100">{node.id}</div>
                </div>

                {/* Agent Name (if applicable) */}
                {node.data.agentName && (
                    <div className="mb-4">
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Agent</label>
                        <div className="text-sm text-gray-900 dark:text-gray-100">{node.data.agentName}</div>
                    </div>
                )}

                {/* Workflow Name (if applicable) */}
                {node.data.workflowName && (
                    <div className="mb-4">
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Workflow
                        </label>
                        <div className="text-sm text-gray-900 dark:text-gray-100">{node.data.workflowName}</div>
                    </div>
                )}

                {/* Condition (for loop/switch) */}
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

                {/* Max Iterations (for loop) */}
                {node.data.maxIterations && (
                    <div className="mb-4">
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">
                            Max Iterations
                        </label>
                        <div className="text-sm text-gray-900 dark:text-gray-100">{node.data.maxIterations}</div>
                    </div>
                )}

                {/* Cases (for switch) */}
                {node.data.cases && node.data.cases.length > 0 && (
                    <div className="mb-4">
                        <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">Cases</label>
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
                                </div>
                            ))}
                            {node.data.defaultCase && (
                                <div className="rounded bg-gray-100 p-2 dark:bg-gray-700">
                                    <div className="mb-1 text-xs font-medium text-gray-600 dark:text-gray-400">
                                        Default
                                    </div>
                                    <div className="text-xs text-gray-800 dark:text-gray-200">
                                        {node.data.defaultCase}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Placeholder message */}
                <div className="mt-8 rounded-lg border border-dashed border-gray-300 p-4 text-center dark:border-gray-600">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        Additional node details will be available in a future update.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default WorkflowNodeDetailPanel;
