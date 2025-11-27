import { useMutation, useQuery } from "@tanstack/react-query";
import { projects } from "./key";
import { addFilesToProject, createProject, getProjects, removeFileFromProject, updateFileMetadata, updateProject } from "./services";
import type { Project, UpdateProjectData } from "@/lib";

export const useProjects = (enabled: boolean) => {
    return useQuery({
        queryKey: projects.all.queryKey,
        queryFn: () => getProjects(),
        enabled,
    });
};

export const useCreateProject = () => {
    return useMutation({
        mutationKey: projects.new.queryKey,
        mutationFn: (project: FormData): Promise<Project> => {
            return createProject(project);
        },
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
    return useMutation({
        mutationKey: projects.update(projectId).queryKey,
        mutationFn: (data: UpdateProjectData) => {
            return updateProject(projectId, data);
        },
    });
};
