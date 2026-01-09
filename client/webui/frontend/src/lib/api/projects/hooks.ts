/**
 * ⚠️ WARNING: THESE HOOKS ARE NOT YET READY FOR USE ⚠️
 *
 * This file contains React Query hooks that are still under development and testing.
 * DO NOT import or use these hooks in your components yet.
 *
 * Current Status:
 * - ❌ Not fully tested
 * - ❌ May have breaking API changes
 * - ❌ Not documented for public use
 * - ❌ Currently being refactored and tested in enterprise
 *
 * When ready for use, this warning will be removed and proper documentation will be added.
 *
 * @internal - These exports are marked as internal and should not be used outside this package
 */

import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateProjectRequest, Project, UpdateProjectData } from "@/lib/types/projects";
import { projectKeys } from "./keys";
import * as projectService from "./service";

/**
 * @internal - DO NOT USE: Still under development
 */
export function useProjects() {
    return useQuery({
        queryKey: projectKeys.lists(),
        queryFn: projectService.getProjects,
    });
}

/** @internal - DO NOT USE: Still under development */
export function useProjectArtifactsNew(projectId: string | null) {
    return useQuery({
        queryKey: projectId ? projectKeys.artifacts(projectId) : ["projects", "artifacts", "empty"],
        queryFn: projectId ? () => projectService.getProjectArtifacts(projectId) : skipToken,
    });
}

/** @internal - DO NOT USE: Still under development */
export function useCreateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectService.createProject(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}

/** @internal - DO NOT USE: Still under development */
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

/** @internal - DO NOT USE: Still under development */
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

/** @internal - DO NOT USE: Still under development */
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

/** @internal - DO NOT USE: Still under development */
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

/** @internal - DO NOT USE: Still under development */
export function useUpdateFileMetadata() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, filename, description }: { projectId: string; filename: string; description: string }) => projectService.updateFileMetadata(projectId, filename, description),
        onSuccess: (_, { projectId }) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.artifacts(projectId) });
        },
    });
}

/** @internal - DO NOT USE: Still under development */
export function useExportProject() {
    return useMutation({
        mutationFn: (projectId: string) => projectService.exportProject(projectId),
    });
}

/** @internal - DO NOT USE: Still under development */
export function useImportProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ file, options }: { file: File; options: { preserveName: boolean; customName?: string } }) => projectService.importProject(file, options),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}
