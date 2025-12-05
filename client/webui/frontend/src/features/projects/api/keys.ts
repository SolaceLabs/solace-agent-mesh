import { createQueryKeys } from "@lukemorales/query-key-factory";

/*
 * Reference for future devs:
 *
 * In the library documentation, there is a less verbose way recommended
 * for creating keys.
 *
 * Example:
 * You can do { all: null, export: (projectId: string) => [projectId] }
 *
 * This is significantly simpler than what's written below.
 *
 * However, this declaration is harder for the compiler to process
 * and it exceeds the max depth for serialization.
 *
 * This doesn't work well with our need to share code between the community
 * and enterprise version, so the more verbose version is recommended.
 */
export const projects = createQueryKeys("projects", {
    all: { queryKey: null },
    create: { queryKey: null },
    import: { queryKey: null },
    update: (projectId: string) => ({ queryKey: [projectId] }),
    delete: (projectId: string) => ({ queryKey: [projectId] }),
    export: (projectId: string) => ({ queryKey: [projectId] }),
    sessions: (projectId: string) => ({ queryKey: [projectId] }),

    artifacts: (projectId: string) => ({
        queryKey: [projectId],
        contextQueries: {
            create: { queryKey: null },
            update: (filename: string) => ({ queryKey: [filename] }),
            delete: (filename: string) => ({ queryKey: [filename] }),
        },
    }),
});
