import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projects } from "./keys";
import { addFilesToProject, createProject, deleteProject, exportProject, getProjectArtifacts, getProjects, getProjectSessions, importProject, removeFileFromProject, updateFileMetadata, updateProject } from "./services";
import { useConfigContext, type Project, type UpdateProjectData } from "@/lib";

const useProjectsConfig = () => {
    const { projectsEnabled } = useConfigContext();
    return Boolean(projectsEnabled);
};

export const useProjects = () => {
    return useQuery({
        queryKey: projects.all.queryKey,
        queryFn: () => getProjects(),
        enabled: useProjectsConfig(),
        select: data => {
            const sorted = [...data.projects].sort((a, b) => {
                return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
            });
            return { ...data, projects: sorted };
        },
    });
};

export const useCreateProject = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.create.queryKey,
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
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.create.queryKey,
        mutationFn: (data: FormData) => addFilesToProject(projectId, data),
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.artifacts(projectId).queryKey,
            }),
    });
};

export const useRemoveFileFromProject = (projectId: string, filename: string) => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.delete(filename).queryKey,
        mutationFn: () => removeFileFromProject(projectId, filename),
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.artifacts(projectId).queryKey,
            }),
    });
};

export const useUpdateFileMetadata = (projectId: string, filename: string) => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.artifacts(projectId)._ctx.update(filename).queryKey,
        mutationFn: (description: string) => updateFileMetadata(projectId, filename, description),
        onSettled: () =>
            queryClient.invalidateQueries({
                queryKey: projects.artifacts(projectId).queryKey,
            }),
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
        enabled: useProjectsConfig(),
        select: data => {
            return [...data].sort((a, b) => {
                const dateA = a.last_modified ? new Date(a.last_modified).getTime() : 0;
                const dateB = b.last_modified ? new Date(b.last_modified).getTime() : 0;
                return dateB - dateA;
            });
        },
    });
};

export const useProjectSessions = (projectId: string) => {
    return useQuery({
        queryKey: projects.sessions(projectId).queryKey,
        queryFn: () => getProjectSessions(projectId),
        enabled: useProjectsConfig(),
    });
};

export const useExportProject = (projectId: string) => {
    return useQuery({
        queryKey: projects.export(projectId).queryKey,
        queryFn: () => exportProject(projectId),
        enabled: false,
        retry: 1,
    });
};

export const useImportProject = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationKey: projects.import.queryKey,
        mutationFn: ({ file, options }: { file: File; options: { preserveName: boolean; customName?: string } }) => importProject(file, options),
        onSuccess: () =>
            queryClient.invalidateQueries({
                queryKey: projects.all.queryKey,
            }),
    });
};
