export interface FeatureFlagInfo {
    key: string;
    name: string;
    release_phase: string;
    resolved: boolean;
    has_env_override: boolean;
    registry_default: boolean;
    description: string;
}
