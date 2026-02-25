import { getArtifactContent as getArtifactContentUtil } from "@/lib/utils/file";

/**
 * Retrieves artifact content for a file in a project.
 * Uses the unified artifact utility with version "latest" to fetch actual file content.
 *
 * @param projectId - The project ID containing the artifact
 * @param filename - The filename of the artifact
 * @returns Promise with content (base64) and mimeType
 */
export async function getArtifactContent(projectId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    // Use the unified utility from @/lib/utils/file.ts
    // This supports both session-scoped and project-scoped artifacts
    return getArtifactContentUtil({
        filename,
        projectId,
        version: "latest", // Fetch latest version
    });
}
