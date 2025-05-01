export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  install_command: string;
}

// Installation status type
export interface InstallStatus {
    loading: boolean;
    success: boolean | null;
    error: string | null;
    output: string | null;
}

// Reusing the existing Step type definition concept
export type Step = {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<{
    // --- Props needed across different steps ---
    // Agent Selection
    availableAgents?: AgentConfig[];
    selectedAgent?: AgentConfig | null;
    onSelectAgent?: (agent: AgentConfig) => void;

    // Agent Naming
    agentName?: string;
    updateAgentName?: (name: string) => void;

    // Installation
    installStatus?: InstallStatus;
    onConfirmInstall?: () => Promise<void>;

    // Navigation / Completion
    onNext?: () => void;
    onPrevious?: () => void;
    onInstallMore?: () => void;
    onExit?: () => void;
  }>;
};