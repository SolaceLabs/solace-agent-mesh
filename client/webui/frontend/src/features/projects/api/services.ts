import type { ArtifactInfo, CreateProjectRequest, Project, UpdateProjectData } from "@/lib";
import type { PaginatedSessionsResponse } from "@/lib/components/chat/SessionList";
import { authenticatedFetch } from "@/lib/utils";

/* TODO:
 * Handle form data instantiation inside service
 * Convert move to different project query
 * Remove Project Provider
 * Add back original error handling
 * */
export const getProjects = async () => {
    const response = await authenticatedFetch("/api/v1/projects?include_artifact_count=true", { credentials: "include" });
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
    return await response.json();
};

export const addFilesToProject = async (projectId: string, data: FormData) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/artifacts`, {
        method: "POST",
        body: data,
        credentials: "include",
    });
    return await response.json();
};

export const removeFileFromProject = async (projectId: string, filename: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, {
        method: "DELETE",
        credentials: "include",
    });
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
    return await response.json();
};

export const updateProject = async (projectId: string, data: UpdateProjectData) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
    });
    return await response.json();
};

export const deleteProject = async (projectId: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}`, {
        method: "DELETE",
        credentials: "include",
    });

    if (!response.ok) {
        throw new Error(`Failed to delete project: ${projectId}`);
    }
};

export const getProjectArtifacts = async (projectId: string) => {
    const url = `/api/v1/projects/${projectId}/artifacts`;
    const response = await authenticatedFetch(url, { credentials: "include" });
    return (await response.json()) as ArtifactInfo[];
};

export const getProjectSessions = async (projectId: string) => {
    const url = `/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`;
    const response = await authenticatedFetch(url, { credentials: "include" });
    const json = (await response.json()) as PaginatedSessionsResponse;
    return json.data;
};

export const exportProject = async (projectId: string) => {
    const response = await authenticatedFetch(`/api/v1/projects/${projectId}/export`);

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to export project");
    }

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

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to import project");
    }
    return await response.json();
};
