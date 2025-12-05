import { createQueryKeys } from "@lukemorales/query-key-factory";

export const projects = createQueryKeys("projects", {
    all: { queryKey: null },
    create: { queryKey: null },
    import: { queryKey: null },
    update: (projectId: string) => ({ queryKey: [projectId] }),
    delete: (projectId: string) => ({ queryKey: [projectId] }),
    export: (projectId: string) => ({ queryKey: [projectId] }),
    sessions: (projectId: string) => ({ queryKey: [projectId] }),

    artifacts: (projectId: string) => ({ queryKey: [projectId, "artifacts"] }),
    artifactsCreate: (projectId: string) => ({ queryKey: [projectId, "artifacts", "create"] }),
    artifactsUpdate: (projectId: string, filename: string) => ({ queryKey: [projectId, "artifacts", "update", filename] }),
    artifactsDelete: (projectId: string, filename: string) => ({ queryKey: [projectId, "artifacts", "delete", filename] }),
});
