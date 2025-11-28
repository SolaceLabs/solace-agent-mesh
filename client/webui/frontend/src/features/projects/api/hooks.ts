import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projects } from "./key";
import { addFilesToProject, createProject, deleteProject, getProjectArtifacts, getProjects, removeFileFromProject, updateFileMetadata, updateProject } from "./services";
import type { Project, UpdateProjectData } from "@/lib";

export const useProjects = (enabled: boolean) => {
    return useQuery({
        queryKey: projects.all.queryKey,
        queryFn: () => getProjects(),
        enabled,
    });
};

export const useCreateProject = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.new.queryKey,
        mutationFn: (project: FormData): Promise<Project> => {
            return createProject(project);
        },
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.all.queryKey,
            }),
    });
};

export const useAddFilesToProject = (projectId: string) => {
    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.new.queryKey,
        mutationFn: (data: FormData) => addFilesToProject(projectId, data),
    });
};

export const useRemoveFileFromProject = (projectId: string) => {
    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.delete.queryKey,
        mutationFn: (filename: string) => removeFileFromProject(projectId, filename),
    });
};

export const useUpdateFileMetadata = (projectId: string) => {
    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.update.queryKey,
        mutationFn: ({ filename, description }: { filename: string; description: string }) => {
            return updateFileMetadata(projectId, filename, description);
        },
    });
};

export const useUpdateProject = (projectId: string) => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.update(projectId).queryKey,
        mutationFn: (data: UpdateProjectData) => {
            return updateProject(projectId, data);
        },
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.all.queryKey,
            }),
    });
};

export const useDeleteProject = (projectId: string) => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.delete(projectId).queryKey,
        mutationFn: () => deleteProject(projectId),
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.all.queryKey,
            }),
    });
};

export const useProjectArtifacts = (projectId: string) => {
    return useQuery({
        queryKey: projects.artifacts(projectId).queryKey,
        queryFn: () => getProjectArtifacts(projectId),
        select: data => {
            return [...data].sort((a, b) => {
                const dateA = a.last_modified ? new Date(a.last_modified).getTime() : 0;
                const dateB = b.last_modified ? new Date(b.last_modified).getTime() : 0;
                return dateB - dateA;
            });
        },
    });
};
