import React from "react";
import type { ReactNode } from "react";

import { GitMerge, Info, Book, Link, Paperclip, Box, Wrench, Key, Bot, Code, Workflow } from "lucide-react";

import type { AgentCardInfo, AgentSkill } from "@/lib/types";
import { isWorkflowAgent, getWorkflowNodeCount } from "@/lib/utils/agentUtils";

interface DetailItemProps {
    label: string;
    value?: string | null | ReactNode;
    icon?: ReactNode;
    fullWidthValue?: boolean;
}

interface AgentDisplayCardProps {
    agent: AgentCardInfo;
    isExpanded: boolean;
    onToggleExpand: () => void;
}

const DetailItem: React.FC<DetailItemProps> = ({ label, value, icon, fullWidthValue = false }) => {
    if (value === undefined || value === null || (typeof value === "string" && !value.trim())) return null;
    return (
        <div className={`mb-1.5 flex text-sm ${fullWidthValue ? "flex-col items-start" : "items-center"}`}>
            <div className="flex w-36 flex-shrink-0 items-center text-sm font-semibold text-nowrap">
                {icon && <span className="mr-2">{icon}</span>}
                {label}:
            </div>
            <div className={`text-accent-foreground text-sm ${fullWidthValue ? "mt-1 w-full" : "truncate"}`} title={typeof value === "string" ? value : undefined}>
                {value}
            </div>
        </div>
    );
};

export const AgentDisplayCard: React.FC<AgentDisplayCardProps> = ({ agent, isExpanded, onToggleExpand }) => {
    const isWorkflow = isWorkflowAgent(agent);
    const nodeCount = isWorkflow ? getWorkflowNodeCount(agent) : 0;

    const renderCapabilities = (capabilities?: { [key: string]: unknown } | null) => {
        if (!capabilities || Object.keys(capabilities).length === 0) return <span className="text-sm">N/A</span>;
        return (
            <ul className="list-inside list-disc pl-1">
                {Object.entries(capabilities).map(([key, value]) => (
                    <li key={key} className="text-sm">
                        <span className="capitalize">{key.replace(/_/g, " ")}:</span> {value ? "Yes" : "No"}
                    </li>
                ))}
            </ul>
        );
    };

    const renderList = (items?: string[] | null, emptyText = "None") => {
        if (!items || items.length === 0) return <span>{emptyText}</span>;
        return items.map(item => (
            <span key={item} className="mr-1 mb-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium">
                {item}
            </span>
        ));
    };

    const renderSkills = (skills?: Array<{ id: string; name: string; description: string }> | null) => {
        if (!skills || skills.length === 0) return <span>No skills listed</span>;
        return (
            <div className="space-y-1">
                {skills.map(skill => (
                    <div key={skill.id || skill.name} className="rounded p-1.5 text-xs">
                        <p className="font-semibold">{skill.name}</p>
                        <p>{skill.description}</p>
                    </div>
                ))}
            </div>
        );
    };

    const renderTools = (tools?: Array<AgentSkill> | null) => {
        if (!tools || tools.length === 0) return <span>No tools listed</span>;
        return (
            <div className="space-y-1">
                {tools.map(tool => (
                    <div key={tool.name} className="rounded p-1.5 text-xs">
                        <p className="text-foreground font-semibold">{tool.name}</p>
                        <p className="mb-1">{tool.description}</p>
                    </div>
                ))}
            </div>
        );
    };

    return (
        <div className="bg-card h-[400px] w-full flex-shrink-0 cursor-pointer rounded-lg sm:w-[380px]" onClick={onToggleExpand} role="button" tabIndex={0} aria-expanded={isExpanded}>
            {/* Front face */}
            <div className={`transform-style-preserve-3d relative h-full w-full transition-transform duration-700 ${isExpanded ? "rotate-y-180" : ""}`} style={{ transformStyle: "preserve-3d" }}>
                <div className="absolute flex h-full w-full flex-col overflow-hidden rounded-lg border shadow-xl" style={{ backfaceVisibility: "hidden", transform: "rotateY(0deg)" }}>
                    <div className="flex items-center p-4">
                        <div className="flex min-w-0 items-center flex-1">
                            {isWorkflow ? (
                                <Workflow className="mr-3 h-8 w-8 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                            ) : (
                                <Bot className="mr-3 h-8 w-8 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                            )}
                            <div className="min-w-0">
                                <h2 className="truncate text-xl font-semibold" title={agent.name}>
                                    {agent.displayName || agent.name}
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div className="scrollbar-themed flex-grow space-y-3 overflow-y-auto p-4">
                        <div className="mb-2 line-clamp-4 text-base">{agent.description || "No description provided."}</div>
                        <DetailItem label="Version" value={agent.version} icon={<GitMerge size={14} />} />
                        {agent.capabilities && Object.keys(agent.capabilities).length > 0 && <DetailItem label="Key Capabilities" value={renderCapabilities(agent.capabilities as { [key: string]: unknown })} icon={<Key size={14} />} fullWidthValue />}
                    </div>
                    <div data-testid="clickForDetails" className="text-accent-foreground border-t p-2 text-center text-sm">
                        Click for details
                    </div>
                </div>

                {/* Back face */}
                <div className="absolute flex h-full w-full flex-col overflow-hidden rounded-lg border shadow-xl" style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
                    <div className="flex items-center p-3">
                        <h3 className="text-md truncate font-semibold" title={agent.name}>
                            Details: {agent.displayName || agent.name}
                        </h3>
                    </div>
                    <div className="scrollbar-themed flex-grow space-y-1.5 overflow-y-auto p-3 text-xs">
                        <DetailItem label="Name" value={agent.name} icon={<Info size={14} />} />
                        <DetailItem label="Description" value={agent.description} icon={<Book size={14} />} fullWidthValue />
                        <DetailItem label="Version" value={agent.version} icon={<GitMerge size={14} />} />
                        <DetailItem label="Endpoint" value={agent.url || "N/A"} icon={<Link size={14} />} />
                        <DetailItem
                            label="Docs"
                            value={
                                agent.documentationUrl ? (
                                    <a href={agent.documentationUrl} target="_blank" rel="noopener noreferrer" className="break-all">
                                        View Docs
                                    </a>
                                ) : (
                                    "N/A"
                                )
                            }
                            icon={<Paperclip size={14} />}
                        />
                        {agent.provider && (
                            <div className="mt-1.5 border-t pt-1.5">
                                <h4 className="mb-0.5 text-xs font-semibold">Provider</h4>
                                <DetailItem label="Name" value={agent.provider.organization} />
                                <DetailItem label="URL" value={agent.provider.url || "N/A"} />
                            </div>
                        )}
                        <DetailItem label="Capabilities" value={renderCapabilities(agent.capabilities as { [key: string]: unknown })} icon={<Key size={14} />} fullWidthValue />
                        <DetailItem label="Input Modes" value={renderList(agent.defaultInputModes)} icon={<Box size={14} />} fullWidthValue />
                        <DetailItem label="Output Modes" value={renderList(agent.defaultOutputModes)} icon={<Box size={14} />} fullWidthValue />
                        <DetailItem label="Skills" value={renderSkills(agent.skills)} icon={<Wrench size={14} />} fullWidthValue />
                        <DetailItem label="Tools Info" value={renderTools(agent.tools)} icon={<Code size={14} />} fullWidthValue />
                        {isWorkflow && nodeCount > 0 && (
                            <div className="mt-3 border-t pt-3">
                                <h4 className="mb-2 text-xs font-semibold">Workflow Information</h4>
                                <DetailItem label="Nodes" value={`${nodeCount} nodes`} icon={<Workflow size={14} />} />
                            </div>
                        )}
                        <div className="text-2xs mt-1.5 pt-1.5">
                            <DetailItem label="A2A Protocol" value={agent.protocolVersion} />
                        </div>
                    </div>
                    <div className="text-accent-foreground border-t p-2 text-center text-sm">Click for summary</div>
                </div>
            </div>
        </div>
    );
};
