import React, { useState } from "react";

import { Button } from "@/lib/components/ui";
import type { AgentCardInfo } from "@/lib/types";

import { AgentDisplayCard } from "./AgentDisplayCard";

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
        <div>
            {agents.length === 0 ? (
                <div className="flex h-[calc(100vh-250px)] items-center justify-center">No agents discovered in the current namespace.</div>
            ) : (
                <div className="mx-auto mt-[50px] ml-[50px]">
                    <div className="my-4">
                        <input type="text" data-testid="agent-search-input" placeholder="Search..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="bg-background rounded-md border px-3 py-2" />
                    </div>
                    {filteredAgents.length === 0 && searchQuery ? (
                        <div className="flex h-[calc(100vh-250px)] flex-col items-center justify-center gap-6">
                            No agents match your search.
                            <Button variant="outline" title="Clear Search" onClick={() => setSearchQuery("")}>
                                Clear Search
                            </Button>
                        </div>
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
        </div>
    );
};
