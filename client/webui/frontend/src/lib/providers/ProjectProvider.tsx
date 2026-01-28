/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useEffect, useState, useMemo } from "react";

import { useConfigContext } from "@/lib/hooks";
import type { Project, ProjectContextValue, UpdateProjectData } from "@/lib/types/projects";
import { useProjects, useCreateProject, useUpdateProject, useDeleteProject, useAddFilesToProject, useRemoveFileFromProject, useUpdateFileMetadata } from "@/lib/api/projects/hooks";

const LAST_VIEWED_PROJECT_KEY = "lastViewedProjectId";

export const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

type OnProjectDeletedCallback = (projectId: string) => void;
let onProjectDeletedCallback: OnProjectDeletedCallback | null = null;

export const registerProjectDeletedCallback = (callback: OnProjectDeletedCallback) => {
    onProjectDeletedCallback = callback;
};

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { projectsEnabled } = useConfigContext();

    // React Query hooks
    const { data: projectsData, isLoading, error: queryError, refetch } = useProjects();
    const createProjectMutation = useCreateProject();
    const updateProjectMutation = useUpdateProject();
    const deleteProjectMutation = useDeleteProject();
    const addFilesMutation = useAddFilesToProject();
    const removeFileMutation = useRemoveFileFromProject();
    const updateFileMetadataMutation = useUpdateFileMetadata();

    // UI-specific state
    const [currentProject, setCurrentProject] = useState<Project | null>(null);
    const [selectedProject, setSelectedProject] = useState<Project | null>(null);
    const [activeProject, setActiveProject] = useState<Project | null>(null);
    const [searchQuery, setSearchQuery] = useState<string>("");

    // Derive projects and error from React Query
    const projects = useMemo(() => {
        if (!projectsEnabled || !projectsData) return [];
        return [...projectsData.projects].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
    }, [projectsData, projectsEnabled]);

    const error = queryError ? (queryError instanceof Error ? queryError.message : "Could not load projects.") : null;

    // Computed filtered projects based on search query
    const filteredProjects = useMemo(() => {
        if (!searchQuery.trim()) return projects;

        const query = searchQuery.toLowerCase();
        return projects.filter(project => project.name.toLowerCase().includes(query) || (project.description?.toLowerCase().includes(query) ?? false));
    }, [projects, searchQuery]);

    // Wrapper for refetch to maintain compatibility
    const fetchProjects = useCallback(async () => {
        if (!projectsEnabled) {
            return;
        }
        await refetch();
    }, [projectsEnabled, refetch]);

    const createProject = useCallback(
        async (projectData: FormData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const name = projectData.get("name") as string;
            const description = projectData.get("description") as string | undefined;

            const newProject = await createProjectMutation.mutateAsync({ name, description: description || undefined });
            return newProject;
        },
        [projectsEnabled, createProjectMutation]
    );

    const addFilesToProject = useCallback(
        async (projectId: string, formData: FormData): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            // Extract files from FormData
            const files = formData.getAll("files") as File[];
            const fileMetadataStr = formData.get("fileMetadata") as string | null;
            const fileMetadata = fileMetadataStr ? JSON.parse(fileMetadataStr) : undefined;

            try {
                await addFilesMutation.mutateAsync({ projectId, files, fileMetadata });
            } catch (error: unknown) {
                // Handle 413 (Payload Too Large) errors specifically
                const errorMessage = error instanceof Error ? error.message : String(error);

                // Check if error message indicates 413 or contains size-related keywords
                if (
                    errorMessage.includes("413") ||
                    errorMessage.toLowerCase().includes("payload too large") ||
                    errorMessage.toLowerCase().includes("exceed") ||
                    errorMessage.toLowerCase().includes("too large") ||
                    errorMessage.toLowerCase().includes("maximum allowed size")
                ) {
                    throw new Error("One or more files exceed the maximum allowed size. Please try uploading smaller files.");
                }
                throw error;
            }
        },
        [projectsEnabled, addFilesMutation]
    );

    const removeFileFromProject = useCallback(
        async (projectId: string, filename: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            await removeFileMutation.mutateAsync({ projectId, filename });
        },
        [projectsEnabled, removeFileMutation]
    );

    const updateFileMetadata = useCallback(
        async (projectId: string, filename: string, description: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            await updateFileMetadataMutation.mutateAsync({ projectId, filename, description });
        },
        [projectsEnabled, updateFileMetadataMutation]
    );

    const updateProject = useCallback(
        async (projectId: string, data: UpdateProjectData): Promise<Project> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            const updatedProject = await updateProjectMutation.mutateAsync({ projectId, data });

            // Update local UI state
            setCurrentProject(current => (current?.id === updatedProject.id ? updatedProject : current));
            setSelectedProject(current => (current?.id === updatedProject.id ? updatedProject : current));
            setActiveProject(current => (current?.id === updatedProject.id ? updatedProject : current));

            return updatedProject;
        },
        [projectsEnabled, updateProjectMutation]
    );

    const deleteProject = useCallback(
        async (projectId: string): Promise<void> => {
            if (!projectsEnabled) {
                throw new Error("Projects feature is disabled");
            }

            await deleteProjectMutation.mutateAsync(projectId);

            // Update local UI state
            setCurrentProject(current => (current?.id === projectId ? null : current));
            setSelectedProject(selected => (selected?.id === projectId ? null : selected));
            setActiveProject(active => (active?.id === projectId ? null : active));

            if (onProjectDeletedCallback) {
                onProjectDeletedCallback(projectId);
            }
        },
        [projectsEnabled, deleteProjectMutation]
    );

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
