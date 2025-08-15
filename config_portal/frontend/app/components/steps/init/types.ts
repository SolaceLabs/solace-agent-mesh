export interface PathSelectionData {
  setupPath: "quick" | "advanced" | null;
}

export interface ProjectSetupData {
  namespace: string;
}

export interface DatabaseSetupData {
  database_url: string;
}

export interface BrokerSetupData {
  broker_type: string;
  broker_url: string;
  broker_vpn: string;
  broker_username: string;
  broker_password?: string;
  container_engine?: "docker" | "podman";
}

export interface AIProviderSetupData {
  llm_provider: string;
  llm_endpoint_url: string;
  llm_api_key?: string;
  llm_planning_model_name: string;
  llm_general_model_name: string;
}

export interface OrchestratorSetupData {
  agent_name: string;
  supports_streaming: boolean;
  session_service_type: "memory" | "vertex_rag";
  session_service_behavior: "PERSISTENT" | "RUN_BASED";
  artifact_service_type: "memory" | "filesystem" | "gcs";
  artifact_service_base_path: string;
  artifact_service_scope: "namespace" | "app" | "custom";
  artifact_handling_mode: "ignore" | "embed" | "reference";
  enable_embed_resolution: boolean;
  enable_artifact_content_instruction: boolean;
  enable_builtin_artifact_tools: boolean;
  enable_builtin_data_tools: boolean;
  agent_card_description: string;
  agent_card_default_input_modes: string[];
  agent_card_default_output_modes: string[];
  agent_discovery_enabled: boolean;
  agent_card_publishing_interval: number;
  inter_agent_communication_allow_list: string[];
  inter_agent_communication_deny_list: string[];
  inter_agent_communication_timeout: number;
}

export interface WebUIGatewaySetupData {
  add_webui_gateway: boolean;
  webui_session_secret_key: string;
  webui_fastapi_host: string;
  webui_fastapi_port: number;
  webui_enable_embed_resolution: boolean;
  webui_frontend_welcome_message: string;
  webui_frontend_bot_name: string;
  webui_frontend_collect_feedback: boolean;
}

export type InitializationData = PathSelectionData &
  ProjectSetupData &
  DatabaseSetupData &
  BrokerSetupData &
  AIProviderSetupData &
  OrchestratorSetupData &
  WebUIGatewaySetupData & {
    showSuccess?: boolean;
  };
