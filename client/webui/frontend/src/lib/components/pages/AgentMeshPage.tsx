import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { Button, EmptyState, Header } from "@/lib/components";
import { AgentMeshCards } from "@/lib/components/agents";
import { WorkflowList } from "@/lib/components/workflows";
import { useChatContext } from "@/lib/hooks";
import { isWorkflowAgent } from "@/lib/utils/agentUtils";
import { RefreshCcw } from "lucide-react";

type AgentMeshTab = "agents" | "workflows";

export function AgentMeshPage() {
    const { agents, agentsLoading, agentsError, agentsRefetch } = useChatContext();
    const [searchParams, setSearchParams] = useSearchParams();

    // Read active tab from URL, default to "agents"
    const activeTab: AgentMeshTab = (searchParams.get("tab") as AgentMeshTab) || "agents";

    const setActiveTab = (tab: AgentMeshTab) => {
        if (tab === "agents") {
            // Remove tab param for default tab
            searchParams.delete("tab");
        } else {
            searchParams.set("tab", tab);
        }
        setSearchParams(searchParams);
    };

    const { regularAgents, workflowAgents } = useMemo(() => {
        const regular = agents.filter(agent => !isWorkflowAgent(agent));
        const workflows = agents.filter(agent => isWorkflowAgent(agent));
        return { regularAgents: regular, workflowAgents: workflows };
    }, [agents]);

    const tabs = [
        {
            id: "agents",
            label: "Agents",
            isActive: activeTab === "agents",
            onClick: () => setActiveTab("agents"),
        },
        {
            id: "workflows",
            label: "Workflows",
            isActive: activeTab === "workflows",
            onClick: () => setActiveTab("workflows"),
        },
    ];

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Agent Mesh"
                tabs={tabs}
                buttons={[
                    <Button key="refresh" data-testid="refreshAgents" disabled={agentsLoading} variant="ghost" title="Refresh Agents" onClick={() => agentsRefetch()}>
                        <RefreshCcw className="size-4" />
                        Refresh
                    </Button>,
                ]}
            />

            {agentsLoading ? (
                <EmptyState title="Loading..." variant="loading" />
            ) : agentsError ? (
                <EmptyState variant="error" title="Error loading data" subtitle={agentsError} />
            ) : (
                <div className="relative min-h-0 flex-1 overflow-hidden">{activeTab === "agents" ? <AgentMeshCards agents={regularAgents} /> : <WorkflowList workflows={workflowAgents} />}</div>
            )}
        </div>
    );
}
