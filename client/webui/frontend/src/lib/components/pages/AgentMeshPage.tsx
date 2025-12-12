import { Button, EmptyState, Header } from "@/lib/components";
import { AgentMeshCards } from "@/lib/components/agents";
import { useChatContext } from "@/lib/hooks";
import { RefreshCcw } from "lucide-react";

export function AgentMeshPage() {
    const { agents, agentsLoading, agentsError, agentsRefetch } = useChatContext();

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Agents"
                buttons={[
                    <Button data-testid="refreshAgents" disabled={agentsLoading} variant="ghost" title="Refresh Agents" onClick={() => agentsRefetch()}>
                        <RefreshCcw className="size-4" />
                        Refresh Agents
                    </Button>,
                ]}
            />

            {agentsLoading ? (
                <EmptyState title="Loading agents..." variant="loading" />
            ) : agentsError ? (
                <EmptyState variant="error" title="Error loading agents" subtitle={agentsError} />
            ) : (
                <div className="relative flex-1">
                    <AgentMeshCards agents={agents} />
                </div>
            )}
        </div>
    );
}
