import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useConfigContext } from "@/lib/hooks";
import type { Project, ProjectContextValue, ProjectListResponse, UpdateProjectData } from "@/lib/types/projects";
import { authenticatedFetch } from "@/lib/utils/api";

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

type OnProjectDeletedCallback = (projectId: string) => void;
let onProjectDeletedCallback: OnProjectDeletedCallback | null = null;

export const registerProjectDeletedCallback = (callback: OnProjectDeletedCallback) => {
    onProjectDeletedCallback = callback;
};

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { configServerUrl, projectsEnabled } = useConfigContext();
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [currentProject, setCurrentProject] = useState<Project | null>(null);
    const [selectedProject, setSelectedProject] = useState<Project | null>(null);
    const [activeProject, setActiveProject] = useState<Project | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchProjects = useCallback(async () => {
        if (!projectsEnabled) {
            setIsLoading(false);
            setProjects([]);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${apiPrefix}/projects`, {
                credentials: "include",
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: `Failed to fetch projects: ${response.statusText}`,
                }));
                throw new Error(errorData.detail || `Failed to fetch projects: ${response.statusText}`);
            }

            const data: ProjectListResponse = await response.json();
            // Sort projects by updatedAt (or createdAt if updatedAt is not available) in descending order
            const sortedProjects = [...data.projects].sort((a, b) => {
                const dateA = new Date(a.updatedAt || a.createdAt).getTime();
                const dateB = new Date(b.updatedAt || b.createdAt).getTime();
                return dateB - dateA; // Descending order (latest first)
            });
            setProjects(sortedProjects);
        } catch (err: unknown) {
            console.error("Error fetching projects:", err);
            setError(err instanceof Error ? err.message : "Could not load projects.");
            setProjects([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix, projectsEnabled]);

    const createProject = useCallback(
        async (projectData: FormData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/projects`, {
                    method: "POST",
                    // No 'Content-Type' header, browser will set it for FormData
                    body: projectData,
                    credentials: "include",
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to create project: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to create project: ${response.statusText}`);
                }

                const newProject: Project = await response.json();

                // Update local state
                setProjects(prev => [newProject, ...prev]);

                return newProject;
            } catch (err: unknown) {
                console.error("Error creating project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not create project.";
                setError(errorMessage);
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
    );

    const addFilesToProject = useCallback(
        async (projectId: string, formData: FormData): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/projects/${projectId}/artifacts`, {
                    method: "POST",
                    body: formData,
                    credentials: "include",
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to add files: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to add files: ${response.statusText}`);
                }
            } catch (err: unknown) {
                console.error("Error adding files to project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not add files to project.";
                setError(errorMessage);
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
    );

    const removeFileFromProject = useCallback(
        async (projectId: string, filename: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                    credentials: "include",
                });

                if (!response.ok && response.status !== 204) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to remove file: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to remove file: ${response.statusText}`);
                }
            } catch (err: unknown) {
                console.error("Error removing file from project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not remove file from project.";
                setError(errorMessage);
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
    );

    const updateProject = useCallback(
        async (projectId: string, data: UpdateProjectData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/projects/${projectId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data),
                    credentials: "include",
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to update project: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to update project: ${response.statusText}`);
                }

                const updatedProject: Project = await response.json();

                // Update projects list and re-sort
                setProjects(prev => {
                    const updated = prev.map(p => (p.id === updatedProject.id ? updatedProject : p));
                    return updated.sort((a, b) => {
                        const dateA = new Date(a.updatedAt || a.createdAt).getTime();
                        const dateB = new Date(b.updatedAt || b.createdAt).getTime();
                        return dateB - dateA; // Descending order (latest first)
                    });
                });
                // Update current project if it's the one being edited
                setCurrentProject(current => (current?.id === updatedProject.id ? updatedProject : current));
                // Update selected project if it's the one being edited
                setSelectedProject(current => (current?.id === updatedProject.id ? updatedProject : current));
                // Update active project if it's the one being edited
                setActiveProject(current => (current?.id === updatedProject.id ? updatedProject : current));

                return updatedProject;
            } catch (err: unknown) {
                console.error("Error updating project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not update project.";
                setError(errorMessage);
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
    );

    const deleteProject = useCallback(
        async (projectId: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/projects/${projectId}`, {
                    method: "DELETE",
                    credentials: "include",
                });

                if (!response.ok && response.status !== 204) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to delete project: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to delete project: ${response.statusText}`);
                }

                setProjects(prev => prev.filter(p => p.id !== projectId));
                
                setCurrentProject(current => (current?.id === projectId ? null : current));
                setSelectedProject(selected => (selected?.id === projectId ? null : selected));
                setActiveProject(active => (active?.id === projectId ? null : active));
                
                if (onProjectDeletedCallback) {
                    onProjectDeletedCallback(projectId);
                }
            } catch (err: unknown) {
                console.error("Error deleting project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not delete project.";
                setError(errorMessage);
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
    );

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    const value: ProjectContextValue = {
        projects,
        isLoading,
        error,
        createProject,
        refetch: fetchProjects,
        currentProject,
        setCurrentProject,
        selectedProject,
        setSelectedProject,
        activeProject,
        setActiveProject,
        addFilesToProject,
        removeFileFromProject,
        updateProject,
        deleteProject,
    };

    return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
};

export const useProjectContext = () => {
    const context = useContext(ProjectContext);
    if (context === undefined) {
        throw new Error("useProjectContext must be used within a ProjectProvider");
    }
    return context;
};
