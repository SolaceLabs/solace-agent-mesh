import { useEffect } from "react";
import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateProjectRequest, Project, UpdateProjectData } from "@/lib/types/projects";
import type { ArtifactInfo } from "@/lib/types";
import { projectKeys } from "./keys";
import * as projectService from "./service";

/**
 * Checks if an artifact is an intermediate web content artifact from deep research.
 * These are temporary files that should not be shown in the files tab.
 *
 * @param filename The filename of the artifact to check.
 * @returns True if the artifact is an intermediate web content artifact.
 */
const isIntermediateWebContentArtifact = (filename: string | undefined): boolean => {
    if (!filename) return false;
    // Skip web_content_ artifacts (temporary files from deep research)
    return filename.startsWith("web_content_");
};

export function useProjects() {
    return useQuery({
        queryKey: projectKeys.lists(),
        queryFn: projectService.getProjects,
    });
}

export function useProjectArtifacts(projectId: string | null) {
    return useQuery({
        queryKey: projectId ? projectKeys.artifacts(projectId) : ["projects", "artifacts", "empty"],
        queryFn: projectId ? () => projectService.getProjectArtifacts(projectId) : skipToken,
        select: (data: ArtifactInfo[]) => {
            return data.filter(artifact => !isIntermediateWebContentArtifact(artifact.filename));
        },
    });
}

export function useProjectSessions(projectId: string | null) {
    const queryClient = useQueryClient();

    // Set up event listeners for automatic invalidation
    // Each hook instance manages its own listeners
    useEffect(() => {
        const handleSessionEvent = () => {
            if (projectId) {
                queryClient.invalidateQueries({ queryKey: projectKeys.sessions(projectId) });
            }
        };

        window.addEventListener("session-moved", handleSessionEvent);
        window.addEventListener("new-chat-session", handleSessionEvent);

        return () => {
            window.removeEventListener("session-moved", handleSessionEvent);
            window.removeEventListener("new-chat-session", handleSessionEvent);
        };
    }, [projectId, queryClient]);

    return useQuery({
        queryKey: projectId ? projectKeys.sessions(projectId) : ["projects", "sessions", "empty"],
        queryFn: projectId ? () => projectService.getProjectSessions(projectId) : skipToken,
        refetchOnMount: "always",
    });
}

export function useCreateProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: CreateProjectRequest) => projectService.createProject(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}

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

export function useUpdateFileMetadata() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ projectId, filename, description }: { projectId: string; filename: string; description: string }) => projectService.updateFileMetadata(projectId, filename, description),
        onSuccess: (_, { projectId }) => {
            queryClient.invalidateQueries({ queryKey: projectKeys.artifacts(projectId) });
        },
    });
}

export function useExportProject() {
    return useMutation({
        mutationFn: (projectId: string) => projectService.exportProject(projectId),
    });
}

export function useImportProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ file, options }: { file: File; options: { preserveName: boolean; customName?: string } }) => projectService.importProject(file, options),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
        },
    });
}
