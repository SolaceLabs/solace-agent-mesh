import type { Project, UpdateProjectData } from "@/lib";
import { authenticatedFetch } from "@/lib/utils";

export const getProjects = async () => {
    const response = await authenticatedFetch("/api/v1/projects?include_artifact_count=true", { credentials: "include" });
    const data = await response.json();
    return data as { projects: Project[]; total: number };
};

export const createProject = async (data: FormData) => {
    const response = await authenticatedFetch("/api/v1/projects", {
        method: "POST",
        body: data,
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
