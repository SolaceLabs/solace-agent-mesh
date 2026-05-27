import React, { useEffect, useRef, useState } from "react";

import type { AgentCardInfo } from "@/lib/types";

import { AgentDisplayCard } from "./AgentDisplayCard";
import { EmptyState } from "../common";
import { SearchInput } from "@/lib/components/ui";
import { Bot } from "lucide-react";

const AgentImage = <Bot className="text-(--secondary-text-wMain)" size={64} />;

interface AgentMeshCardsProps {
    agents: AgentCardInfo[];
    selectedAgent?: string | null;
}

export const AgentMeshCards: React.FC<AgentMeshCardsProps> = ({ agents, selectedAgent }) => {
    const [expandedAgentName, setExpandedAgentName] = useState<string | null>(selectedAgent ?? null);
    const [searchQuery, setSearchQuery] = useState<string>("");
    const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

    // Honor deep-links arriving (or changing) after mount: expand the targeted
    // agent, clear any active filter that would hide it, and scroll it into view.
    // Guarded by a ref so a polling refetch of `agents` doesn't clobber the
    // user's manual selection — only react when the deep-link value itself
    // changes. The scroll is deferred via requestAnimationFrame because
    // setSearchQuery("") may unhide the targeted card; the ref isn't attached
    // until after the next render, so reading it synchronously here would
    // return null.
    const lastAppliedSelection = useRef<string | null>(null);
    const pendingScrollTarget = useRef<string | null>(null);
    useEffect(() => {
        if (!selectedAgent) return;
        if (lastAppliedSelection.current === selectedAgent) return;
        if (!agents.some(a => a.name === selectedAgent)) return;
        lastAppliedSelection.current = selectedAgent;
        setExpandedAgentName(selectedAgent);
        setSearchQuery("");
        pendingScrollTarget.current = selectedAgent;
    }, [selectedAgent, agents]);

    // Run the scroll on the next frame after the targeted card has been
    // rendered and its ref attached. Watching filteredAgents/searchQuery
    // ensures we re-check after the filter clear flushes.
    useEffect(() => {
        const target = pendingScrollTarget.current;
        if (!target) return;
        const raf = requestAnimationFrame(() => {
            const node = cardRefs.current[target];
            if (node) {
                node.scrollIntoView({ behavior: "smooth", block: "center" });
                pendingScrollTarget.current = null;
            }
        });
        return () => cancelAnimationFrame(raf);
    }, [searchQuery, agents]);

    const handleToggleExpand = (agentName: string) => {
        setExpandedAgentName(prev => (prev === agentName ? null : agentName));
    };

    const filteredAgents = agents.filter(agent => (agent.displayName || agent.name)?.toLowerCase().includes(searchQuery.toLowerCase()));

    return (
        <>
            {agents.length === 0 ? (
                <EmptyState image={AgentImage} title="No agents found" subtitle="No agents discovered in the current namespace." />
            ) : (
                <div className="flex h-full w-full flex-col pt-6 pb-6 pl-6">
                    <SearchInput value={searchQuery} onChange={setSearchQuery} testid="agentSearchInput" className="mb-4 w-xs flex-shrink-0" />

                    {filteredAgents.length === 0 && searchQuery ? (
                        <EmptyState variant="notFound" title="No Agents Match Your Filter" subtitle="Try adjusting your filter terms." buttons={[{ text: "Clear Filter", variant: "default", onClick: () => setSearchQuery("") }]} />
                    ) : (
                        <div className="min-h-0 flex-1 overflow-y-auto">
                            <div className="flex flex-wrap gap-10">
                                {filteredAgents.map(agent => (
                                    <div
                                        key={agent.name}
                                        ref={node => {
                                            cardRefs.current[agent.name] = node;
                                        }}
                                        className="w-full sm:w-auto"
                                    >
                                        <AgentDisplayCard agent={agent} isExpanded={expandedAgentName === agent.name} onToggleExpand={() => handleToggleExpand(agent.name)} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </>
    );
};
