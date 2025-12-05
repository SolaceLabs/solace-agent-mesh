import React, { createContext, useCallback, useContext, useEffect, useState, useMemo } from "react";

import { useConfigContext } from "@/lib/hooks";
import type { Project, ProjectContextValue, ProjectListResponse, UpdateProjectData } from "@/lib/types/projects";
import { authenticatedFetch } from "@/lib/utils/api";

const LAST_VIEWED_PROJECT_KEY = "lastViewedProjectId";

export const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

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
    const [searchQuery, setSearchQuery] = useState<string>("");

    const apiPrefix = `${configServerUrl}/api/v1`;

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
            // Fetch projects with artifact counts
            const response = await authenticatedFetch(`${apiPrefix}/projects?include_artifact_count=true`, {
                credentials: "include",
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: `Failed to fetch projects: ${response.statusText}`,
                }));
                throw new Error(errorData.detail || `Failed to fetch projects: ${response.statusText}`);
            }

            const data: ProjectListResponse = await response.json();
            // Sort projects alphabetically by name (case-insensitive)
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
                    const responseText = await response.text();

                    let errorMessage = `Failed to create project: ${response.statusText}`;
                    try {
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.detail || errorData.message || errorMessage;
                    } catch {
                        if (responseText && responseText.length < 200) {
                            errorMessage = responseText;
                        }
                    }
                    throw new Error(errorMessage);
                }

                const newProject: Project = await response.json();

                // Update local state with alphabetical sorting
                setProjects(prev => {
                    const updated = [newProject, ...prev];
                    return updated.sort((a, b) => {
                        return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                    });
                });

                return newProject;
            } catch (err: unknown) {
                const errorMessage = err instanceof Error ? err.message : "Could not create project.";
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
                    const responseText = await response.text();
                    let errorMessage = `Failed to add files: ${response.statusText}`;

                    try {
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.detail || errorData.message || errorMessage;
                    } catch {
                        // If JSON parsing fails, check if we have a meaningful response text
                        if (responseText && responseText.length < 500) {
                            errorMessage = responseText;
                        }
                    }

                    // Provide user-friendly message for file size errors
                    if (response.status === 413) {
                        // If we have a detailed message from the backend, use it
                        // Otherwise provide a generic but helpful message
                        if (!errorMessage.includes("exceeds maximum") && !errorMessage.includes("too large")) {
                            errorMessage = "One or more files exceed the maximum allowed size. Please try uploading smaller files.";
                        }
                    }

                    throw new Error(errorMessage);
                }
                // Clear any previous errors on success
                setError(null);

                // Refetch projects to update artifact counts
                await fetchProjects();
            } catch (err: unknown) {
                console.error("Error adding files to project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not add files to project.";
                // Don't set global error for file operations - let component handle it
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled, fetchProjects]
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
                // Clear any previous errors on success
                setError(null);

                // Refetch projects to update artifact counts
                await fetchProjects();
            } catch (err: unknown) {
                console.error("Error removing file from project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not remove file from project.";
                // Don't set global error for file operations - let component handle it
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled, fetchProjects]
    );

    const updateFileMetadata = useCallback(
        async (projectId: string, filename: string, description: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            try {
                const formData = new FormData();
                formData.append("description", description);

                const response = await authenticatedFetch(`${apiPrefix}/projects/${projectId}/artifacts/${encodeURIComponent(filename)}`, {
                    method: "PATCH",
                    body: formData,
                    credentials: "include",
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({
                        detail: `Failed to update file metadata: ${response.statusText}`,
                    }));
                    throw new Error(errorData.detail || `Failed to update file metadata: ${response.statusText}`);
                }
                // Clear any previous errors on success
                setError(null);
            } catch (err: unknown) {
                console.error("Error updating file metadata:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not update file metadata.";
                // Don't set global error for file operations - let component handle it
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
                    let errorMessage = `Failed to update project: ${response.statusText}`;

                    try {
                        const errorData = await response.json();

                        // Handle validation errors (422)
                        if (response.status === 422) {
                            if (errorData.detail) {
                                // Check if it's a Pydantic validation error array
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
                        // If JSON parsing fails, use the default error message
                    }

                    throw new Error(errorMessage);
                }

                const updatedProject: Project = await response.json();

                // Update projects list and re-sort alphabetically
                setProjects(prev => {
                    const updated = prev.map(p => (p.id === updatedProject.id ? updatedProject : p));
                    return updated.sort((a, b) => {
                        return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
                    });
                });
                // Update current project if it's the one being edited
                setCurrentProject(current => (current?.id === updatedProject.id ? updatedProject : current));
                // Update selected project if it's the one being edited
                setSelectedProject(current => (current?.id === updatedProject.id ? updatedProject : current));
                // Update active project if it's the one being edited
                setActiveProject(current => (current?.id === updatedProject.id ? updatedProject : current));

                // Clear any previous errors on success
                setError(null);

                return updatedProject;
            } catch (err: unknown) {
                console.error("Error updating project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not update project.";
                // Don't set global error state for update failures - let the component handle it
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

                // Clear any previous errors on success
                setError(null);

                if (onProjectDeletedCallback) {
                    onProjectDeletedCallback(projectId);
                }
            } catch (err: unknown) {
                console.error("Error deleting project:", err);
                const errorMessage = err instanceof Error ? err.message : "Could not delete project.";
                // Don't set global error for delete operations - let component handle it
                throw new Error(errorMessage);
            }
        },
        [apiPrefix, projectsEnabled]
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
