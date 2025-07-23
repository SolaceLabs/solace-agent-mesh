export interface PyProjectAuthor {
  name?: string | null;
  email?: string | null;
}

export interface PyProjectDetails {
  name: string;
  version: string;
  description?: string | null;
  authors?: PyProjectAuthor[] | null;
  plugin_type?: string | null;
  custom_metadata?: Record<string, unknown> | null;
}

export interface AgentCardSkill {
  name: string;
  description?: string | null;
}

export interface AgentCard {
  displayName?: string | null;
  shortDescription?: string | null;
  Skill?: AgentCardSkill[] | null;
}

export interface PluginViewData {
  id: string;
  pyproject: PyProjectDetails;
  readme_content?: string | null;
  agent_card?: AgentCard | null;
  source_registry_name?: string | null;
  source_registry_location: string;
  source_type: "git" | "local";
  plugin_subpath: string;
  is_official: boolean;
}

export interface RegistryViewData {
  id: string;
  path_or_url: string;
  name?: string | null;
  type: "git" | "local";
  is_default: boolean;
  is_official_source: boolean;
}
