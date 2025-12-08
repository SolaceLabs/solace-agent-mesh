import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";
import { fetchJsonWithError, fetchWithError } from "@/lib/utils";

export const getProjects = async () => {
    const url = "/api/v1/projects?include_artifact_count=true";
    const response = await fetchJsonWithError(url, { credentials: "include" });

    return response as { projects: Project[]; total: number };
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    const url = "/api/v1/projects";
    const response = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
        credentials: "include",
    });

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

    const url = `/api/v1/projects/${projectId}/artifacts`;
    const response = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
        credentials: "include",
    });

    return response;
};

export const removeFileFromProject = async (projectId: string, filename: string) => {
    const url = `/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`;
    const response = await fetchJsonWithError(url, {
        method: "DELETE",
        credentials: "include",
    });

    return response;
};

export const updateFileMetadata = async (projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    const url = `/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`;
    const response = await fetchJsonWithError(url, {
        method: "PATCH",
        body: formData,
        credentials: "include",
    });

    return response;
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    const url = `/api/v1/projects/${projectId}`;
    const response = await fetchJsonWithError(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
    });

    return response;
};

export const deleteProject = async (projectId: string) => {
    const url = `/api/v1/projects/${projectId}`;
    await fetchWithError(url, {
        method: "DELETE",
        credentials: "include",
    });
};

export const getProjectArtifacts = async (projectId: string) => {
    const url = `/api/v1/projects/${projectId}/artifacts`;
    const response = (await fetchJsonWithError(url, { credentials: "include" })) as ArtifactInfo[];

    return response;
};

export const getProjectSessions = async (projectId: string) => {
    const url = `/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`;
    const response = (await fetchJsonWithError(url, { credentials: "include" })) as PaginatedSessionsResponse;

    return response.data;
};

export const exportProject = async (projectId: string) => {
    const url = `/api/v1/projects/${projectId}/export`;

    const response = await fetchWithError(url);

    return await response.blob();
};

export const importProject = async (file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const url = "/api/v1/projects/import";
    const result = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
    });

    return result;
};
