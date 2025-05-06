import React from 'react';

export interface AgentConfig {
    id: string;
    plugin_agent_name: string;
    name: string;
    description: string;
    install_command: string;
}

export interface InstallStatus {
    loading: boolean;
    success: boolean | null;
    error: string | null;
    output: string | null;
}

export interface SchemaDefinition {
    type: 'string' | 'number' | 'boolean' | 'dict' | 'list' | 'any';
    nullable?: boolean;
    item_schema?: SchemaDefinition | null;
    properties?: { [key: string]: SchemaDefinition };
    key_order?: string[];
}

interface BaseConfigParam {
    name: string;
    editable: boolean;
}

export interface SimpleConfigParam extends BaseConfigParam {
    type: 'simple';
    schema: SchemaDefinition;
    current_value_str: string;
    is_env_var: boolean;
    env_var_name?: string | null;
    env_var_default?: string | null;
    literal_value?: string | number | boolean | null;
    data_type?: string;
}

export interface ListConfigParam extends BaseConfigParam {
    type: 'list';
    schema: SchemaDefinition & { type: 'list' };
    values: any[];
    item_type?: 'simple' | 'complex';
}

export interface DictConfigParam extends BaseConfigParam {
    type: 'dict';
    schema: SchemaDefinition & { type: 'dict' };
    value: Record<string, any>;
}

export type ConfigParam = SimpleConfigParam | ListConfigParam | DictConfigParam;

export interface AgentConfigurationResponse {
    status: 'success' | 'error';
    agent_name: string;
    config_params: ConfigParam[];
    message?: string;
}

export interface UpdateAgentConfigurationResponse {
    status: 'success' | 'error';
    message?: string;
}

export type StepComponentProps = {
    availableAgents: AgentConfig[];
    selectedAgent: AgentConfig | null;
    onSelectAgent: (agent: AgentConfig) => void;
    agentName: string;
    updateAgentName: (name: string) => void;
    installStatus: InstallStatus;
    onConfirmInstall: () => Promise<void>;
    onNext: () => void;
    onPrevious: () => void;
    onInstallMore: () => void;
    onExit: () => void;
};

export type Step = {
    id: string;
    title: string;
    description: string;
    component: React.ComponentType<StepComponentProps>;
};