import { createQueryKeys } from "@lukemorales/query-key-factory";

export const projects = createQueryKeys("projects", {
    all: null,
    import: null,
    new: null,

    delete: (projectId: string) => [projectId],
    update: (projectId: string) => [projectId],
    export: (projectId: string) => [projectId],
    artifacts: (projectID: string) => ({
        queryKey: [projectID],
        contextQueries: {
            detail: (filename: string) => [filename],
            new: null,
            delete: null,
            update: null,
        },
    }),
});

