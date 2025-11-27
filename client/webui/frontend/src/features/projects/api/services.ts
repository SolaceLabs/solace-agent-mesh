import type { Project } from "@/lib";
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
