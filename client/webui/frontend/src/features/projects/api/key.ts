import { createQueryKeys } from "@lukemorales/query-key-factory";

export const projects = createQueryKeys("projects", {
    all: null,
    import: null,
    new: null,
    export: (projectId: string) => [projectId],
    artifacts: (projectID: string) => ({
        queryKey: [projectID],
        contextQueries: {
            artifact: (filename: string) => [filename],
        },
    }),
});

