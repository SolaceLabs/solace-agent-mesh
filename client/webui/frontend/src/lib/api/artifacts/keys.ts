/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const artifactKeys = {
    all: ["artifacts"] as const,
    content: (sessionId: string | null, projectId: string | null, filename: string, version?: number) => [...artifactKeys.all, "content", sessionId, projectId, filename, version] as const,
    pdfBlob: (url: string) => [...artifactKeys.all, "pdf-blob", url] as const,
};
