/**
 * App types for SAM Apps feature.
 */

export interface App {
    id: string;
    appId: string;
    userId: string;
    name: string;
    description: string | null;
    workspaceId: string;
    isPublic: boolean;
    isOwner?: boolean;  // Optional for backwards compatibility with older backends
    createdByUserId: string;
    status: "draft" | "deployed" | "archived";
    currentVersion: number;
    devVersion: string | null;
    stagingVersion: string | null;
    prodVersion: string | null;
    iconEmoji: string | null;
    iconBackground: string | null;
    createdTime: number;
    updatedTime: number;
    archivedTime: number | null;
    tags: string[];
}

export interface CreateAppRequest {
    name: string;
    description?: string;
}

export interface CreateAppResponse {
    appId: string;
    workspaceId: string;
    workspacePath: string;
    status: string;
    iconEmoji: string | null;
    iconBackground: string | null;
}

export interface DeployAppResponse {
    success: boolean;
    version: number;
    errors: string[] | null;
}

export type Environment = "dev" | "staging" | "prod";

export interface PreviewVersionInfo {
    version: string | null;
    available: boolean;
}

export interface EnvironmentVersions {
    dev: string | null;
    staging: string | null;
    prod: string | null;
}

export interface AppVersionsResponse {
    versions: string[];
    preview: PreviewVersionInfo;
    environments: EnvironmentVersions;
}

export interface PromoteVersionResponse {
    success: boolean;
    version: string;
    environment: Environment;
    error: string | null;
}
