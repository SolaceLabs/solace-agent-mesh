/**
 * Project-related types matching the backend DTOs
 */

export interface Project {
    id: string;
    name: string;
    userId: string;
    description?: string | null;
    systemPrompt?: string | null;
    defaultAgentId?: string | null;
    artifactCount?: number | null;
    createdAt: string; // ISO string
    updatedAt: string; // ISO string
}

export interface CreateProjectRequest {
    name: string;
    description?: string;
    system_prompt?: string;
    files?: FileList | null;
}

export interface CopyProjectRequest {
    name: string;
    description?: string;
}

export interface UpdateProjectData {
    name?: string;
    description?: string;
    systemPrompt?: string;
    defaultAgentId?: string | null;
}

export interface ProjectListResponse {
    projects: Project[];
    total: number;
}

// Frontend-only types
export interface ProjectFormData {
    name: string;
    description: string;
    system_prompt: string;
    defaultAgentId?: string;
    files?: FileList | null;
    fileDescriptions?: Record<string, string>;
}

export interface ProjectContextValue {
    activeProject: Project | null;
    setActiveProject: (project: Project | null) => void;
}
