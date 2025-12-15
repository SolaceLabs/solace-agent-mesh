import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";
import { fetchJsonWithError, fetchWithError } from "@/lib/utils";

export const getProjects = async (baseUrl: string) => {
    const url = `${baseUrl}/api/v1/projects?include_artifact_count=true`;
    const response = await fetchJsonWithError(url);

    return response as { projects: Project[]; total: number };
};

export const createProject = async (baseUrl: string, data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    const url = `${baseUrl}/api/v1/projects`;
    const response = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
    });

    return response;
};

export const addFilesToProject = async (baseUrl: string, projectId: string, files: File[], fileMetadata?: Record<string, string>) => {
    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const url = `${baseUrl}/api/v1/projects/${projectId}/artifacts`;
    const response = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
    });

    return response;
};

export const removeFileFromProject = async (baseUrl: string, projectId: string, filename: string) => {
    const url = `${baseUrl}/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`;
    const response = await fetchJsonWithError(url, {
        method: "DELETE",
    });

    return response;
};

export const updateFileMetadata = async (baseUrl: string, projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    const url = `${baseUrl}/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`;
    const response = await fetchJsonWithError(url, {
        method: "PATCH",
        body: formData,
    });

    return response;
};

export const updateProject = async (baseUrl: string, projectId: string, data: UpdateProjectData) => {
    const url = `${baseUrl}/api/v1/projects/${projectId}`;
    const response = await fetchJsonWithError(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

    return response;
};

export const deleteProject = async (baseUrl: string, projectId: string) => {
    const url = `${baseUrl}/api/v1/projects/${projectId}`;
    await fetchWithError(url, {
        method: "DELETE",
    });
};

export const getProjectArtifacts = async (baseUrl: string, projectId: string) => {
    const url = `${baseUrl}/api/v1/projects/${projectId}/artifacts`;
    const response = (await fetchJsonWithError(url)) as ArtifactInfo[];

    return response;
};

export const getProjectSessions = async (baseUrl: string, projectId: string) => {
    const url = `${baseUrl}/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`;
    const response = (await fetchJsonWithError(url)) as PaginatedSessionsResponse;

    return response.data;
};

export const exportProject = async (baseUrl: string, projectId: string) => {
    const url = `${baseUrl}/api/v1/projects/${projectId}/export`;

    const response = await fetchWithError(url);

    return await response.blob();
};

export const importProject = async (baseUrl: string, file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const url = `${baseUrl}/api/v1/projects/import`;
    const result = await fetchJsonWithError(url, {
        method: "POST",
        body: formData,
    });

    return result;
};
