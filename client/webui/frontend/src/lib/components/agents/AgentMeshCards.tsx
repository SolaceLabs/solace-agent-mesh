import React, { useState } from "react";

import type { AgentCardInfo } from "@/lib/types";

import { AgentDisplayCard } from "./AgentDisplayCard";
import { EmptyState } from "../common";
import { SearchInput } from "@/lib/components/ui";
import { Bot } from "lucide-react";

const AgentImage = <Bot className="text-muted-foreground" size={64} />;

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
                <EmptyState image={AgentImage} title="No agents found" subtitle="No agents discovered in the current namespace." />
            ) : (
                <div className="bg-card-background flex h-full w-full flex-col pt-6 pb-6 pl-6">
                    <SearchInput value={searchQuery} onChange={setSearchQuery} placeholder="Filter by name..." testid="agentSearchInput" className="mb-4 w-xs flex-shrink-0" />

                    {filteredAgents.length === 0 && searchQuery ? (
                        <EmptyState variant="notFound" title="No Agents Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchQuery("") }]} />
                    ) : (
                        <div className="min-h-0 flex-1 overflow-y-auto">
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
