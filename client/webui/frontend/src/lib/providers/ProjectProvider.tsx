import React, { createContext, useCallback, useContext, useEffect, useState, useMemo } from "react";

import { useConfigContext } from "@/lib/hooks";
import type { Project, ProjectContextValue, ProjectListResponse, UpdateProjectData, Collaborator, ProjectRole, CollaboratorsResponse } from "@/lib/types/projects";
import { api } from "@/lib/api";
import {
    shareProject as apiShareProject,
    getCollaborators as apiGetCollaborators,
    getCollaboratorsWithOwner as apiGetCollaboratorsWithOwner,
    updateCollaborator as apiUpdateCollaborator,
    removeCollaborator as apiRemoveCollaborator,
} from "@/lib/api/projects/sharing";

const LAST_VIEWED_PROJECT_KEY = "lastViewedProjectId";

export const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

type OnProjectDeletedCallback = (projectId: string) => void;
let onProjectDeletedCallback: OnProjectDeletedCallback | null = null;

export const registerProjectDeletedCallback = (callback: OnProjectDeletedCallback) => {
    onProjectDeletedCallback = callback;
};

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { projectsEnabled } = useConfigContext();
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [currentProject, setCurrentProject] = useState<Project | null>(null);
    const [selectedProject, setSelectedProject] = useState<Project | null>(null);
    const [activeProject, setActiveProject] = useState<Project | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");

    // Computed filtered projects based on search query
    const filteredProjects = useMemo(() => {
        if (!searchQuery.trim()) return projects;

        const query = searchQuery.toLowerCase();
        return projects.filter(project => project.name.toLowerCase().includes(query) || (project.description?.toLowerCase().includes(query) ?? false));
    }, [projects, searchQuery]);

    const fetchProjects = useCallback(async () => {
        if (!projectsEnabled) {
            setIsLoading(false);
            setProjects([]);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const data: ProjectListResponse = await api.webui.get("/api/v1/projects?include_artifact_count=true");
            const sortedProjects = [...data.projects].sort((a, b) => {
                return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            });
            setProjects(sortedProjects);
        } catch (err: unknown) {
            console.error("Error fetching projects:", err);
            setError(err instanceof Error ? err.message : "Could not load projects.");
            setProjects([]);
        } finally {
            setIsLoading(false);
        }
    }, [projectsEnabled]);

    const createProject = useCallback(
        async (projectData: FormData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const newProject: Project = await api.webui.post("/api/v1/projects", projectData);

            setProjects(prev => {
                const updated = [newProject, ...prev];
                return updated.sort((a, b) => {
                    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                });
            });

            return newProject;
        },
        [projectsEnabled]
    );

    const addFilesToProject = useCallback(
        async (projectId: string, formData: FormData): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const response = await api.webui.post(`/api/v1/projects/${projectId}/artifacts`, formData, { fullResponse: true });

            if (!response.ok) {
                const responseText = await response.text();
                let errorMessage = `Failed to add files: ${response.statusText}`;

                try {
                    const errorData = JSON.parse(responseText);
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch {
                    if (responseText && responseText.length < 500) {
                        errorMessage = responseText;
                    }
                }

                if (response.status === 413) {
                    if (!errorMessage.includes("exceeds maximum") && !errorMessage.includes("too large")) {
                        errorMessage = "One or more files exceed the maximum allowed size. Please try uploading smaller files.";
                    }
                }

                throw new Error(errorMessage);
            }

            setError(null);
            await fetchProjects();
        },
        [projectsEnabled, fetchProjects]
    );

    const removeFileFromProject = useCallback(
        async (projectId: string, filename: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            await api.webui.delete(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`);
            setError(null);
            await fetchProjects();
        },
        [projectsEnabled, fetchProjects]
    );

    const updateFileMetadata = useCallback(
        async (projectId: string, filename: string, description: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const formData = new FormData();
            formData.append("description", description);

            await api.webui.patch(`/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, formData);
            setError(null);
        },
        [projectsEnabled]
    );

    const updateProject = useCallback(
        async (projectId: string, data: UpdateProjectData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const response = await api.webui.put(`/api/v1/projects/${projectId}`, data, { fullResponse: true });

            if (!response.ok) {
                let errorMessage = `Failed to update project: ${response.statusText}`;

                try {
                    const errorData = await response.json();

                    if (response.status === 422) {
                        if (errorData.detail) {
                            if (Array.isArray(errorData.detail)) {
                                const validationErrors = errorData.detail
                                    .map((err: { loc?: string[]; msg: string }) => {
                                        const field = err.loc?.join(".") || "field";
                                        return `${field}: ${err.msg}`;
                                    })
                                    .join(", ");
                                errorMessage = `Validation error: ${validationErrors}`;
                            } else if (typeof errorData.detail === "string") {
                                errorMessage = errorData.detail;
                            }
                        }
                    } else {
                        errorMessage = errorData.detail || errorData.message || errorMessage;
                    }
                } catch {
                    // JSON parsing failed, use default error message
                }

                throw new Error(errorMessage);
            }

            const updatedProject: Project = await response.json();

            setProjects(prev => {
                const updated = prev.map(p => (p.id === updatedProject.id ? updatedProject : p));
                return updated.sort((a, b) => {
                    return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                });
            });
            setCurrentProject(current => (current?.id === updatedProject.id ? updatedProject : current));
            setSelectedProject(current => (current?.id === updatedProject.id ? updatedProject : current));
            setActiveProject(current => (current?.id === updatedProject.id ? updatedProject : current));
            setError(null);

            return updatedProject;
        },
        [projectsEnabled]
    );

    const deleteProject = useCallback(
        async (projectId: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            await api.webui.delete(`/api/v1/projects/${projectId}`);

            setProjects(prev => prev.filter(p => p.id !== projectId));
            setCurrentProject(current => (current?.id === projectId ? null : current));
            setSelectedProject(selected => (selected?.id === projectId ? null : selected));
            setActiveProject(active => (active?.id === projectId ? null : active));
            setError(null);

            if (onProjectDeletedCallback) {
                onProjectDeletedCallback(projectId);
            }
        },
        [projectsEnabled]
    );

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    // Restore last viewed project from localStorage
    useEffect(() => {
        if (projects.length > 0 && !selectedProject) {
            const savedProjectId = localStorage.getItem(LAST_VIEWED_PROJECT_KEY);
            if (savedProjectId) {
                const project = projects.find(p => p.id === savedProjectId);
                if (project) {
                    setSelectedProject(project);
                }
            }
        }
    }, [projects, selectedProject]);

    // Enhanced setSelectedProject that persists to localStorage
    const handleSetSelectedProject = useCallback((project: Project | null) => {
        setSelectedProject(project);
        if (project) {
            localStorage.setItem(LAST_VIEWED_PROJECT_KEY, project.id);
        } else {
            localStorage.removeItem(LAST_VIEWED_PROJECT_KEY);
        }
    }, []);

    // Sharing Methods

    const getCollaborators = useCallback(
        async (projectId: string): Promise<Collaborator[]> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }
            return await apiGetCollaborators(projectId);
        },
        [projectsEnabled]
    );

    const getCollaboratorsWithOwner = useCallback(
        async (projectId: string): Promise<CollaboratorsResponse> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }
            return await apiGetCollaboratorsWithOwner(projectId);
        },
        [projectsEnabled]
    );

    const shareProject = useCallback(
        async (projectId: string, email: string, role: ProjectRole): Promise<Collaborator> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const newCollaborator = await apiShareProject(projectId, email, role);

            // Refetch to update collaborator counts or other derived state if needed
            // For now, we assume local state in dialogs will handle the list, but we can trigger a global refresh if critical
            // We might want to update the project list to reflect sharing status if it changes visually

            return newCollaborator;
        },
        [projectsEnabled]
    );

    const updateCollaborator = useCallback(
        async (projectId: string, userId: string, role: ProjectRole): Promise<Collaborator> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }
            return await apiUpdateCollaborator(projectId, userId, role);
        },
        [projectsEnabled]
    );

    const removeCollaborator = useCallback(
        async (projectId: string, userId: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }
            await apiRemoveCollaborator(projectId, userId);
        },
        [projectsEnabled]
    );

    const value: ProjectContextValue = {
        projects,
        isLoading,
        error,
        createProject,
        refetch: fetchProjects,
        currentProject,
        setCurrentProject,
        selectedProject,
        setSelectedProject: handleSetSelectedProject,
        activeProject,
        setActiveProject,
        addFilesToProject,
        removeFileFromProject,
        updateFileMetadata,
        updateProject,
        deleteProject,
        searchQuery,
        setSearchQuery,
        filteredProjects,
        getCollaborators,
        getCollaboratorsWithOwner,
        shareProject,
        updateCollaborator,
        removeCollaborator,
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
