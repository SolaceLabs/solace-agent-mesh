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
    role?: ProjectRole;
    collaboratorCount?: number;
}

export type ProjectRole = "owner" | "editor" | "viewer";

export interface Collaborator {
    userId: string;
    userEmail: string | null;
    userName: string | null;
    role: ProjectRole;
    addedAt: string | number; // ISO string or timestamp
    addedByUserId?: string;
}

export interface CollaboratorsResponse {
    projectId: string;
    owner: Collaborator;
    collaborators: Collaborator[];
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
    // Sharing methods
    getCollaborators: (projectId: string) => Promise<Collaborator[]>;
    getCollaboratorsWithOwner: (projectId: string) => Promise<CollaboratorsResponse>;
    shareProject: (projectId: string, email: string, role: ProjectRole) => Promise<Collaborator>;
    updateCollaborator: (projectId: string, userId: string, role: ProjectRole) => Promise<Collaborator>;
    removeCollaborator: (projectId: string, userId: string) => Promise<void>;
}

// People search API types
export interface PersonSearchResult {
    id: string;
    name: string;
    email: string;
    title: string | null;
}

export interface PeopleSearchResponse {
    data: PersonSearchResult[];
}

// Pending user (before submission)
export interface PendingCollaborator {
    id: string;
    name: string;
    email: string;
    role: "viewer"; // Always viewer for this POC
}
