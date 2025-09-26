/**
 * Project-related types matching the backend DTOs
 */

export interface Project {
    id: string;
    name: string;
    user_id: string;
    description?: string | null;
    system_prompt?: string | null;
    is_global: boolean;
    template_id?: string | null;
    created_by_user_id: string;
    created_at: string; // ISO string
    updated_at: string; // ISO string
}

export interface GlobalProject {
    id: string;
    name: string;
    description?: string | null;
    created_by_user_id: string;
    created_at: string; // ISO string
    updated_at: string; // ISO string
    usage_count?: number | null;
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
    system_prompt?: string;
}

export interface ProjectListResponse {
    projects: Project[];
    total: number;
}

export interface GlobalProjectListResponse {
    projects: GlobalProject[];
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

export interface UseGlobalProjectsReturn {
    globalProjects: GlobalProject[];
    isLoading: boolean;
    error: string | null;
    copyProject: (templateId: string, data: CopyProjectRequest) => Promise<Project>;
    refetch: () => Promise<void>;
}

export interface ProjectContextValue extends UseProjectsReturn {
    currentProject: Project | null;
    setCurrentProject: (project: Project | null) => void;
    activeProject: Project | null;
    setActiveProject: (project: Project | null) => void;
    addFilesToProject: (projectId: string, formData: FormData) => Promise<void>;
    removeFileFromProject: (projectId: string, filename: string) => Promise<void>;
    updateProject: (projectId: string, data: UpdateProjectData) => Promise<Project>;
}
