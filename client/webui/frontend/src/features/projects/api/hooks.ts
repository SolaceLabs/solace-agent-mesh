import { useQuery } from "@tanstack/react-query";
import { projects } from "./key";
import { getProjects } from "./services";

export const useProjects = (enabled: boolean) => {
    return useQuery({
        queryKey: projects.all.queryKey,
        queryFn: () => getProjects(),
        enabled,
    });
};
