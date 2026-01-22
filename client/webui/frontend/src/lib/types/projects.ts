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

export type ArtifactStreamEventType =
    | "validation_started"
    | "validation_completed"
    | "artifact_saving_started"
    | "artifact_saved"
    | "indexing_started"
    | "index_creation_started"
    | "index_creation_completed"
    | "index_creation_failed"
    | "upload_completed"
    | "upload_failed";

export interface ArtifactStreamEventData {
    type: ArtifactStreamEventType;
    file_count?: number;
    artifact_count?: number;
    filename?: string;
    version?: number;
    index_version?: number;
    progress?: string;
    error?: string;
    total_files?: number;
    timestamp: string;
}

export interface ArtifactStreamEvent {
    event: "upload_progress" | "upload_success" | "upload_error";
    data: ArtifactStreamEventData;
}

export interface UploadProgress {
    phase: "validating" | "saving" | "indexing" | "completed" | "error";
    statusText: string;
    fileCount: number;
    completedFiles: number;
    failedFiles: string[];
    succeededFiles: string[];
}

export interface UploadFilesResult {
    success: boolean;
    totalFiles: number;
    succeededFiles: string[];
    failedFiles: string[];
    error?: string;
}
