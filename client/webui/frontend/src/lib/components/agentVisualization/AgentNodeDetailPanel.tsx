import React from "react";
import { Bot, Wrench, Sparkles, Package } from "lucide-react";
import type { AgentLayoutNode, AgentDiagramConfig } from "./utils/types";

interface AgentNodeDetailPanelProps {
    node: AgentLayoutNode | null;
    config: AgentDiagramConfig;
}

/**
 * AgentNodeDetailPanel - Shows details for the selected agent diagram node.
 * Displays contextual information based on node type.
 */
const AgentNodeDetailPanel: React.FC<AgentNodeDetailPanelProps> = ({ node, config }) => {
    if (!node) return null;

    const getNodeIcon = () => {
        switch (node.type) {
            case "agent-header":
                return <Bot className="h-6 w-6 text-(--color-brand-wMain)" />;
            case "tool":
                return <Wrench className="h-6 w-6 text-(--color-accent-n0-wMain)" />;
            case "skill":
                return <Sparkles className="h-6 w-6 text-(--color-info-wMain)" />;
            case "toolset-group":
                return <Package className="h-6 w-6 text-(--color-accent-n0-wMain)" />;
            default:
                return null;
        }
    };

    const getTypeLabel = () => {
        switch (node.type) {
            case "agent-header":
                return "Agent";
            case "tool":
                return "Tool";
            case "skill":
                return "Skill";
            case "toolset-group":
                return "Toolset Group";
            default:
                return "Node";
        }
    };

    const title = node.data.agentName || node.data.toolName || node.data.skillName || node.data.label;

    return (
        <div className="bg-background flex h-full flex-col" role="complementary" aria-label="Node details panel">
            {/* Header */}
            <div className="flex items-center border-b p-4">
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                    {getNodeIcon()}
                    <span className="truncate pr-2 text-[20px] font-semibold" title={title}>
                        {title}
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="scrollbar-themed flex-1 overflow-auto p-4">
                {/* Type */}
                <div className="mb-4">
                    <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Type</label>
                    <div className="text-sm">{getTypeLabel()}</div>
                </div>

                {/* Agent details */}
                {node.type === "agent-header" && (
                    <>
                        {config.description && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Description</label>
                                <div className="text-sm">{config.description}</div>
                            </div>
                        )}

                        {config.instruction && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Instruction</label>
                                <div className="scrollbar-themed max-h-64 overflow-auto whitespace-pre-wrap text-sm">{config.instruction}</div>
                            </div>
                        )}

                        {config.inputModes && config.inputModes.length > 0 && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Input Modes</label>
                                <div className="flex flex-wrap gap-1.5">
                                    {config.inputModes.map(mode => (
                                        <span key={mode} className="rounded bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-700">
                                            {mode}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {config.outputModes && config.outputModes.length > 0 && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Output Modes</label>
                                <div className="flex flex-wrap gap-1.5">
                                    {config.outputModes.map(mode => (
                                        <span key={mode} className="rounded bg-gray-100 px-2 py-0.5 text-xs dark:bg-gray-700">
                                            {mode}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Tool details */}
                {node.type === "tool" && (
                    <>
                        {node.data.toolType && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Tool Type</label>
                                <div className="text-sm">{node.data.toolType}</div>
                            </div>
                        )}
                        {node.data.toolDescription && (
                            <div className="mb-4">
                                <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Description</label>
                                <div className="text-sm">{node.data.toolDescription}</div>
                            </div>
                        )}
                    </>
                )}

                {/* Skill details */}
                {node.type === "skill" && node.data.skillDescription && (
                    <div className="mb-4">
                        <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Description</label>
                        <div className="text-sm">{node.data.skillDescription}</div>
                    </div>
                )}

                {/* Toolset group details */}
                {node.type === "toolset-group" && node.data.groupName && (
                    <div className="mb-4">
                        <label className="mb-1 block text-sm font-medium text-(--color-secondary-text-wMain)">Group ID</label>
                        <code className="font-mono text-sm">{node.data.groupName}</code>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentNodeDetailPanel;
