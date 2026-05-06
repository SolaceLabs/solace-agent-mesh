import type { ArtifactInfo, FileAttachment, MessageFE } from "@/lib/types";

/**
 * Returns true if an artifact has been deleted. To be considered deleted:
 * - artifact creation must be completed AND
 * - no matching record exists in the artifact list AND
 * - artifact has no file attachment URI AND
 * - parent message (if provided) must be complete (to avoid false positives for artifacts without content yet)
 */
export function isArtifactDeleted({
    status,
    artifactInfo,
    fileAttachment,
    message,
}: {
    status: "in-progress" | "completed" | "failed";
    artifactInfo: ArtifactInfo | undefined;
    fileAttachment: FileAttachment | undefined;
    message: MessageFE | undefined;
}): boolean {
    if (status !== "completed") return false;
    if (artifactInfo) return false;
    if (fileAttachment?.uri) return false;
    if (message && !message.isComplete) return false;
    return true;
}
