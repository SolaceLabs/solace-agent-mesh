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

export interface UseProjectsReturn {
    projects: Project[];
    isLoading: boolean;
    error: string | null;
    createProject: (data: FormData) => Promise<Project>;
    refetch: () => Promise<void>;
}

export interface ProjectContextValue extends UseProjectsReturn {
    currentProject: Project | null;
    setCurrentProject: (project: Project | null) => void;
    selectedProject: Project | null;
    setSelectedProject: (project: Project | null) => void;
    activeProject: Project | null;
    setActiveProject: (project: Project | null) => void;
    addFilesToProject: (projectId: string, formData: FormData) => Promise<void>;
    removeFileFromProject: (projectId: string, filename: string) => Promise<void>;
    updateFileMetadata: (projectId: string, filename: string, description: string) => Promise<void>;
    updateProject: (projectId: string, data: UpdateProjectData) => Promise<Project>;
    deleteProject: (projectId: string) => Promise<void>;
    searchQuery: string;
    setSearchQuery: (query: string) => void;
    filteredProjects: Project[];
}

// Project Sharing Types

export interface ShareResponse {
    id: string;
    projectId: string;
    userEmail: string;
    accessLevel: string;
    sharedByEmail: string;
    createdAt: string; // ISO 8601 datetime
    updatedAt: string; // ISO 8601 datetime
}

export interface ProjectSharesResponse {
    projectId: string;
    ownerEmail: string;
    shares: ShareResponse[];
}

export interface BatchShareRequest {
    shares: {
        userEmail: string;
        accessLevel: "RESOURCE_VIEWER";
    }[];
}

export interface BatchShareResponse {
    projectId: string;
    created: ShareResponse[];
    updated: ShareResponse[];
    totalProcessed: number;
}

export interface BatchDeleteRequest {
    userEmails: string[];
}

export interface BatchDeleteResponse {
    projectId: string;
    deletedCount: number;
    deletedEmails: string[];
}

export interface UpdateShareRequest {
    accessLevel: "RESOURCE_VIEWER";
}

export type AccessLevel = "RESOURCE_VIEWER";
