import { useState } from "react";

import { Button, EmptyState, Header, LayoutSelector } from "@/lib/components";
import { AgentMeshCards } from "@/lib/components/agents";
import { useChatContext } from "@/lib/hooks";
import { pluginRegistry } from "@/lib/plugins";
import { LayoutType } from "@/lib/types";
import { RefreshCcw } from "lucide-react";

export function AgentMeshPage() {
    const { agents, agentsLoading, agentsError, agentsRefetch } = useChatContext();
    const [currentLayout, setCurrentLayout] = useState<string>("cards");

    const renderLayoutContent = () => {
        if (currentLayout === LayoutType.CARDS) {
            return <AgentMeshCards agents={agents} />;
        }

        // For other layouts, check if the layout exists in the registry
        const layoutPlugin = pluginRegistry.getPluginById(currentLayout);
        if (layoutPlugin) {
            return layoutPlugin.render({ agents });
        } else {
            console.warn(`Layout ${currentLayout} not found, falling back to cards layout`);
            return <AgentMeshCards agents={agents} />;
        }
    };

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
                <div className={`relative flex-1 p-4 ${currentLayout === LayoutType.CARDS ? "" : "bg-[var(--muted)] dark:bg-[var(--color-bg-wMain)]"}`}>
                    <div className="absolute right-8 z-20 flex items-center space-x-4">
                        <LayoutSelector currentLayout={currentLayout} onLayoutChange={setCurrentLayout} />
                    </div>
                    {renderLayoutContent()}
                </div>
            )}
        </div>
    );
}
