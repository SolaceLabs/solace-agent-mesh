import { useState, useEffect, useCallback } from "react";

import type { Project, CreateProjectRequest, ProjectListResponse, UseProjectsReturn } from "@/lib/types/projects";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

export const useProjects = (): UseProjectsReturn => {
    const { configServerUrl } = useConfigContext();
    const [projects, setProjects] = useState<Project[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchProjects = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${apiPrefix}/projects`, { 
                credentials: "include" 
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: `Failed to fetch projects: ${response.statusText}` 
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

    const createProject = useCallback(async (projectData: CreateProjectRequest): Promise<Project> => {
        try {
            const response = await authenticatedFetch(`${apiPrefix}/projects`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(projectData),
                credentials: "include",
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: `Failed to create project: ${response.statusText}` 
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
    }, [apiPrefix]);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    return {
        projects,
        isLoading,
        error,
        createProject,
        refetch: fetchProjects,
    };
};