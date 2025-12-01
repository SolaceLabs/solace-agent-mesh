import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";
import { authenticatedFetch } from "@/lib/utils";

export const handleAPIError = async (response: Response, defaultMessageLabel: string) => {
    if (response.ok) return;

    const errorData = await response.json();

    throw new Error(errorData.message || errorData.detail || `${defaultMessageLabel}: ${response.statusText}`);
};
export const getProjects = async () => {
    const response = await authenticatedFetch("/api/v1/projects?include_artifact_count=true", { credentials: "include" });
    await handleAPIError(response, "Failed to get projects");

    const data = await response.json();
    return data as { projects: Project[]; total: number };
};

export const createProject = async (data: CreateProjectRequest) => {
    const formData = new FormData();
    formData.append("name", data.name);

    if (data.description) {
        formData.append("description", data.description);
    }

    const response = await authenticatedFetch("/api/v1/projects", {
        method: "POST",
        body: formData,
        credentials: "include",
    });

    await handleAPIError(response, "Failed to create project");

    return await response.json();
};

export const addFilesToProject = async (projectId: string, files: File[], fileMetadata?: Record<string, string>) => {
    const formData = new FormData();

    files.forEach(file => {
        formData.append("files", file);
    });

    if (fileMetadata && Object.keys(fileMetadata).length > 0) {
        formData.append("fileMetadata", JSON.stringify(fileMetadata));
    }

    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/artifacts`, {
        method: "POST",
        body: formData,
        credentials: "include",
    });

    await handleAPIError(response, "Failed to add files to project");

    return await response.json();
};

export const removeFileFromProject = async (projectId: string, filename: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, {
        method: "DELETE",
        credentials: "include",
    });

    await handleAPIError(response, "Failed to remove file from project");

    return await response.json();
};

export const updateFileMetadata = async (projectId: string, filename: string, description: string) => {
    const formData = new FormData();
    formData.append("description", description);

    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, {
        method: "PATCH",
        body: formData,
        credentials: "include",
    });

    await handleAPIError(response, "Failed to update file description");

    return await response.json();
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
    });

    await handleAPIError(response, "Failed to update project");

    return await response.json();
};

export const deleteProject = async (projectId: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}`, {
        method: "DELETE",
        credentials: "include",
    });

    await handleAPIError(response, "Failed to delete project");
};

export const getProjectArtifacts = async (projectId: string) => {
    const url = `/api/v1/projects/${projectId}/artifacts`;
    const response = await authenticatedFetch(url, { credentials: "include" });

    await handleAPIError(response, "Failed to get project artifacts");

    return (await response.json()) as ArtifactInfo[];
};

export const getProjectSessions = async (projectId: string) => {
    const url = `/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`;
    const response = await authenticatedFetch(url, { credentials: "include" });

    await handleAPIError(response, "Failed to get project sessions");

    const json = (await response.json()) as PaginatedSessionsResponse;
    return json.data;
};

export const exportProject = async (projectId: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/export`);

    await handleAPIError(response, "Failed to export project");

    return await response.blob();
};

export const importProject = async (file: File, options: { preserveName: boolean; customName?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("options", JSON.stringify(options));

    const response = await authenticatedFetch("/api/v1/projects/import", {
        method: "POST",
        body: formData,
        credentials: "include",
    });

    await handleAPIError(response, "Failed to import project");

    return await response.json();
};
