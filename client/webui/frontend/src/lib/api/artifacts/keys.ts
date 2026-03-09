/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const artifactKeys = {
    all: ["artifacts"] as const,
    content: (sessionId: string, filename: string) => [...artifactKeys.all, "content", sessionId, filename] as const,
    pdfBlob: (url: string) => [...artifactKeys.all, "pdf-blob", url] as const,
};
