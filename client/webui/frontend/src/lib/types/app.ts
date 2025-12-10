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
    status: "draft" | "deployed" | "archived";
    currentVersion: number;
    createdTime: number;
    updatedTime: number;
    archivedTime: number | null;
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
}

export interface DeployAppResponse {
    success: boolean;
    version: number;
    errors: string[] | null;
}
