import React, { createContext, useCallback, useContext, useEffect, useState } from "react";

import { useConfigContext } from "@/lib/hooks";
import type { Project, ProjectContextValue, ProjectListResponse } from "@/lib/types/projects";
import { authenticatedFetch } from "@/lib/utils/api";

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { configServerUrl } = useConfigContext();
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [currentProject, setCurrentProject] = useState<Project | null>(null);
    const [activeProject, setActiveProject] = useState<Project | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchProjects = useCallback(async () => {
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
            setProjects(data.projects);
        } catch (err: unknown) {
            console.error("Error fetching projects:", err);
            setError(err instanceof Error ? err.message : "Could not load projects.");
            setProjects([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix]);

    const createProject = useCallback(
        async (projectData: FormData): Promise<Project> => {
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
        [apiPrefix]
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
        activeProject,
        setActiveProject,
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
