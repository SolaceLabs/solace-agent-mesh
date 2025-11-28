import { createQueryKeys } from "@lukemorales/query-key-factory";

export const projects = createQueryKeys("projects", {
    all: null,

    create: null,
    update: (projectId: string) => [projectId],
    delete: (projectId: string) => [projectId],
    import: null,
    export: (projectId: string) => [projectId],

    artifacts: (projectId: string) => ({
        queryKey: [projectId],
        contextQueries: {
            create: null,
            update: (filename: string) => [filename],
            delete: (filename: string) => [filename],
        },
    }),

    sessions: (projectId: string) => [projectId],
});
