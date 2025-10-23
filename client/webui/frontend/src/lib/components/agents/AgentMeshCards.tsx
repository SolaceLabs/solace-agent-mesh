import React, { useState } from "react";

import type { AgentCardInfo } from "@/lib/types";

import { AgentDisplayCard } from "./AgentDisplayCard";
import { EmptyState } from "../common";

interface AgentMeshCardsProps {
    agents: AgentCardInfo[];
}

export const AgentMeshCards: React.FC<AgentMeshCardsProps> = ({ agents }) => {
    const [expandedAgentName, setExpandedAgentName] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");

    const handleToggleExpand = (agentName: string) => {
        setExpandedAgentName(prev => (prev === agentName ? null : agentName));
    };

    const filteredAgents = agents.filter(agent => (agent.displayName || agent.name)?.toLowerCase().includes(searchQuery.toLowerCase()));

    return (
        <>
            {agents.length === 0 ? (
                <EmptyState variant="noImage" title="No agents found" subtitle="No agents discovered in the current namespace." />
            ) : (
                <div className="h-full w-full pt-12 pl-12">
                    <input type="text" data-testid="agentSearchInput" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="bg-background mb-4 rounded-md border px-3 py-2" />

                    {filteredAgents.length === 0 && searchQuery ? (
                        <EmptyState title="No agents match your search" variant="noImage" buttons={[{ text: "Clear Search", variant: "default", onClick: () => setSearchQuery("") }]} />
                    ) : (
                        <div className="max-h-[calc(100vh-250px)] overflow-y-auto">
                            <div className="flex flex-wrap gap-10">
                                {filteredAgents.map(agent => (
                                    <AgentDisplayCard key={agent.name} agent={agent} isExpanded={expandedAgentName === agent.name} onToggleExpand={() => handleToggleExpand(agent.name)} />
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </>
    );
};
