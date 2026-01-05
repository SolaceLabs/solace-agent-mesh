import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateProjectRequest, Project, UpdateProjectData } from "@/lib/types/projects";
import { projectKeys } from "./keys";
import * as projectService from "./service";

/**
 * Query hook for fetching all projects
 */
export function useProjects() {
    return useQuery({
        queryKey: projectKeys.lists(),
        queryFn: projectService.getProjects,
    });
}

/**
 * Query hook for fetching project artifacts
 */
export function useProjectArtifacts(projectId: string | null) {
    return useQuery({
        queryKey: projectId ? projectKeys.artifacts(projectId) : ["projects", "artifacts", "empty"],
        queryFn: projectId ? () => projectService.getProjectArtifacts(projectId) : skipToken,
    });
}

/**
 * Mutation hook for creating a new project
 */
export function useCreateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectService.createProject(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}

/**
 * Mutation hook for updating a project
 */
export function useUpdateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, data }: { projectId: string; data: UpdateProjectData }) => projectService.updateProject(projectId, data),
        onSuccess: (updatedProject: Project) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
            queryClient.invalidateQueries({ queryKey: projectKeys.detail(updatedProject.id) });
        },
    });
}

/**
 * Mutation hook for deleting a project
 */
export function useDeleteProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (projectId: string) => projectService.deleteProject(projectId),
        onSuccess: (_, projectId) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
            queryClient.removeQueries({ queryKey: projectKeys.detail(projectId) });
        },
    });
}

/**
 * Mutation hook for adding files to a project
 */
export function useAddFilesToProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, files, fileMetadata }: { projectId: string; files: File[]; fileMetadata?: Record<string, string> }) => projectService.addFilesToProject(projectId, files, fileMetadata),
        onSuccess: (_, { projectId }) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
            queryClient.invalidateQueries({ queryKey: projectKeys.artifacts(projectId) });
        },
    });
}

/**
 * Mutation hook for removing a file from a project
 */
export function useRemoveFileFromProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, filename }: { projectId: string; filename: string }) => projectService.removeFileFromProject(projectId, filename),
        onSuccess: (_, { projectId }) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
            queryClient.invalidateQueries({ queryKey: projectKeys.artifacts(projectId) });
        },
    });
}

/**
 * Mutation hook for updating file metadata
 */
export function useUpdateFileMetadata() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, filename, description }: { projectId: string; filename: string; description: string }) => projectService.updateFileMetadata(projectId, filename, description),
        onSuccess: (_, { projectId }) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.artifacts(projectId) });
        },
    });
}

/**
 * Mutation hook for exporting a project
 */
export function useExportProject() {
    return useMutation({
        mutationFn: (projectId: string) => projectService.exportProject(projectId),
    });
}

/**
 * Mutation hook for importing a project
 */
export function useImportProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ file, options }: { file: File; options: { preserveName: boolean; customName?: string } }) => projectService.importProject(file, options),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}
