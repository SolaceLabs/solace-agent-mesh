/**
 * Project-related types matching the backend DTOs
 */

export interface Project {
    id: string;
    name: string;
    userId: string;
    description?: string | null;
    systemPrompt?: string | null;
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
    updateProject: (projectId: string, data: UpdateProjectData) => Promise<Project>;
    deleteProject: (projectId: string) => Promise<void>;
}
