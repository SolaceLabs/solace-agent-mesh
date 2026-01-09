import { api } from "@/lib/api";
import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";

export const getProjects = async () => {
    const response = await api.webui.get<{ projects: Project[]; total: number }>("/api/v1/projects?include_artifact_count=true");
    return response;
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    const response = await api.webui.post<Project>("/api/v1/projects", formData);
    return response;
};

export const addFilesToProject = async (projectId: string, files: File[], fileMetadata?: Record<string, string>) => {
    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const response = await api.webui.post(`/api/v1/projects/${projectId}/artifacts`, formData);
    return response;
};

export const removeFileFromProject = async (projectId: string, filename: string) => {
    const response = await api.webui.delete(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`);
    return response;
};

export const updateFileMetadata = async (projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    const response = await api.webui.patch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, formData);
    return response;
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    const response = await api.webui.put<Project>(`/api/v1/projects/${projectId}`, data);
    return response;
};

export const deleteProject = async (projectId: string) => {
    await api.webui.delete(`/api/v1/projects/${projectId}`);
};

export const getProjectArtifacts = async (projectId: string) => {
    const response = await api.webui.get<ArtifactInfo[]>(`/api/v1/projects/${projectId}/artifacts`);
    return response;
};

export const getProjectSessions = async (projectId: string) => {
    const response = await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`);
    return response.data;
};

export const exportProject = async (projectId: string) => {
    const response = await api.webui.get(`/api/v1/projects/${projectId}/export`, { fullResponse: true });
    return await response.blob();
};

export const importProject = async (file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const result = await api.webui.post("/api/v1/projects/import", formData);
    return result;
};
