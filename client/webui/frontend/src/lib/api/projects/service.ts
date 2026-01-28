import { api } from "@/lib/api";
import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData, ProjectSharesResponse, BatchShareRequest, BatchShareResponse, BatchDeleteRequest, BatchDeleteResponse, UpdateShareRequest, ShareResponse } from "@/lib";
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

// Project Sharing APIs

export const getProjectShares = async (projectId: string) => {
    const response = await api.webui.get<ProjectSharesResponse>(`/api/v1/projects/${projectId}/shares`);
    return response;
};

export const createProjectShares = async (projectId: string, data: BatchShareRequest) => {
    const response = await api.webui.post<BatchShareResponse>(`/api/v1/projects/${projectId}/shares`, data);
    return response;
};

export const deleteProjectShares = async (projectId: string, data: BatchDeleteRequest) => {
    // Using a custom fetch approach since api.webui.delete doesn't support body parameter
    const response = await fetch(api.webui.getFullUrl(`/api/v1/projects/${projectId}/shares`), {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        throw new Error(`Failed to delete project shares: ${response.statusText}`);
    }

    return (await response.json()) as BatchDeleteResponse;
};

export const updateProjectShare = async (projectId: string, shareId: string, data: UpdateShareRequest) => {
    const response = await api.webui.put<ShareResponse>(`/api/v1/projects/${projectId}/shares/${shareId}`, data);
    return response;
};
