import { useMutation, useQuery } from "@tanstack/react-query";
import { projects } from "./key";
import { createProject, getProjects } from "./services";
import type { Project } from "@/lib";

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
