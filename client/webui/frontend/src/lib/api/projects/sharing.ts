import { api } from "@/lib/api";
import type { Collaborator, ProjectRole } from "@/lib/types/projects";

/**
 * Get all collaborators for a project
 */
export const getCollaborators = async (projectId: string) => {
    const response = await api.webui.get<Collaborator[]>(`/api/v1/projects/${projectId}/collaborators`);
    return response;
};

/**
 * Share a project with a user by email
 */
export const shareProject = async (projectId: string, email: string, role: ProjectRole) => {
    const formData = new FormData();
    formData.append("user_email", email);
    formData.append("role", role);

    const response = await api.webui.post<Collaborator>(`/api/v1/projects/${projectId}/share`, formData);
    return response;
};

/**
 * Update a collaborator's role
 */
export const updateCollaborator = async (projectId: string, userId: string, role: ProjectRole) => {
    const formData = new FormData();
    formData.append("role", role);

    const response = await api.webui.put<Collaborator>(`/api/v1/projects/${projectId}/collaborators/${userId}`, formData);
    return response;
};

/**
 * Remove a collaborator from a project
 */
export const removeCollaborator = async (projectId: string, userId: string) => {
    await api.webui.delete(`/api/v1/projects/${projectId}/collaborators/${userId}`);
};
