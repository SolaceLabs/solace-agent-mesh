import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useBooleanFlagDetails } from "@openfeature/react-sdk";

import { useNavigate } from "react-router-dom";

import { Button, EmptyState, Header } from "@/lib/components";
import { AgentMeshCards } from "@/lib/components/agents";
import { WorkflowList } from "@/lib/components/workflows";
import { ModelsView } from "@/lib/components/models";
import { useChatContext } from "@/lib/hooks";
import { useModelConfigs } from "@/lib/api/models";
import { isWorkflowAgent } from "@/lib/utils/agentUtils";
import { RefreshCcw, Plus } from "lucide-react";

type AgentMeshTab = "agents" | "workflows" | "models";

export function AgentMeshPage() {
    const navigate = useNavigate();
    const { agents, agentsLoading, agentsError, agentsRefetch } = useChatContext();
    const { data: modelConfigs = [] } = useModelConfigs();
    const [searchParams, setSearchParams] = useSearchParams();
    const { value: modelConfigUiEnabled } = useBooleanFlagDetails("model_config_ui", false);

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
            badge: "EXPERIMENTAL",
        },
        ...(modelConfigUiEnabled
            ? [
                  {
                      id: "models",
                      label: "Models",
                      isActive: activeTab === "models",
                      onClick: () => setActiveTab("models"),
                  },
              ]
            : []),
    ];

    const headerButtons = useMemo(() => {
        const buttons = [];

        // Add Model button comes first on models tab
        if (activeTab === "models" && modelConfigs.length > 0) {
            buttons.push(
                <Button key="addModel" data-testid="addModel" variant="ghost" title="Add Model" onClick={() => navigate("/models/new/edit")}>
                    <Plus className="size-4" />
                    Add Model
                </Button>
            );
        }

        // Refresh button
        buttons.push(
            <Button key="refresh" data-testid="refreshAgents" disabled={agentsLoading} variant="ghost" title="Refresh Agents" onClick={() => agentsRefetch()}>
                <RefreshCcw className="size-4" />
                Refresh
            </Button>
        );

        return buttons;
    }, [activeTab, modelConfigs.length, agentsLoading, agentsRefetch, navigate]);

    return (
        <div className="flex h-full w-full flex-col">
            <Header title="Agent Mesh" tabs={tabs} buttons={headerButtons} />

            {agentsLoading ? (
                <EmptyState title="Loading..." variant="loading" />
            ) : agentsError ? (
                <EmptyState variant="error" title="Error loading data" subtitle={agentsError} />
            ) : (
                <div className="relative min-h-0 flex-1 overflow-hidden">
                    {activeTab === "agents" && <AgentMeshCards agents={regularAgents} />}
                    {activeTab === "workflows" && <WorkflowList workflows={workflowAgents} />}
                    {activeTab === "models" && <ModelsView />}
                </div>
            )}
        </div>
    );
}
