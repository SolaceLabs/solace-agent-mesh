import { api, getErrorFromResponse } from "@/lib/api";
import { getApiBearerToken } from "@/lib/utils/api";
import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData, ProjectSharesResponse, BatchShareRequest, BatchShareResponse, BatchDeleteRequest, BatchDeleteResponse } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";

export const getProjects = async () => {
    return api.webui.get<{ projects: Project[]; total: number }>("/api/v1/projects?include_artifact_count=true");
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    return api.webui.post<Project>("/api/v1/projects", formData);
};

export const addFilesToProject = async (projectId: string, files: File[], fileMetadata?: Record<string, string>): Promise<{ sseLocation: string | null }> => {
    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const response = await api.webui.post(`/api/v1/projects/${projectId}/artifacts`, formData, { fullResponse: true });

    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }

    const result = await response.json();
    return { ...result, sseLocation: response.headers.get("sse-location") };
};

export const removeFileFromProject = async (projectId: string, filename: string): Promise<{ sseLocation: string | null }> => {
    const response = await api.webui.delete(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, { fullResponse: true });

    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }

    const result = await response.json();
    return { ...result, sseLocation: response.headers.get("sse-location") };
};

export const updateFileMetadata = async (projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    return api.webui.patch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, formData);
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    return api.webui.put<Project>(`/api/v1/projects/${projectId}`, data);
};

export const deleteProject = async (projectId: string) => {
    await api.webui.delete(`/api/v1/projects/${projectId}`);
};

export const getProjectArtifacts = async (projectId: string) => {
    return api.webui.get<ArtifactInfo[]>(`/api/v1/projects/${projectId}/artifacts`);
};

export const getProjectSessions = async (projectId: string) => {
    return (await api.webui.get<PaginatedSessionsResponse>(`/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`)).data;
};

export const exportProject = async (projectId: string) => {
    const response = await api.webui.get(`/api/v1/projects/${projectId}/export`, { fullResponse: true });
    return await response.blob();
};

export const importProject = async (file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const response = await api.webui.post("/api/v1/projects/import", formData, { fullResponse: true });

    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }

    const result = await response.json();
    return { ...result, sseLocation: response.headers.get("sse-location") };
};

// Project Sharing APIs

export const getProjectShares = async (projectId: string) => {
    return api.webui.get<ProjectSharesResponse>(`/api/v1/projects/${projectId}/shares`);
};

export const createProjectShares = async (projectId: string, data: BatchShareRequest) => {
    return api.webui.post<BatchShareResponse>(`/api/v1/projects/${projectId}/shares`, data);
};

export const deleteProjectShares = async (projectId: string, data: BatchDeleteRequest) => {
    // Using a custom fetch approach since api.webui.delete doesn't support body parameter
    const response = await fetch(api.webui.getFullUrl(`/api/v1/projects/${projectId}/shares`), {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getApiBearerToken()}`,
        },
        body: JSON.stringify(data),
    });

    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }

    return (await response.json()) as BatchDeleteResponse;
};
