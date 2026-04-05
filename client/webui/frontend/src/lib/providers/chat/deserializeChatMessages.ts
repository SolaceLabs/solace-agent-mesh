import type { MessageFE, PartFE } from "@/lib/types";

// ============ Types ============

interface StoredBubble {
    id?: string;
    type: "user" | "agent";
    text?: string;
    parts?: PartFE[];
    files?: File[];
    uploadedFiles?: File[];
    artifactNotification?: unknown;
    isError?: boolean;
    displayHtml?: string;
    contextQuote?: string;
    contextQuoteSourceId?: string;
    sender_display_name?: string;
    sender_email?: string;
    progressUpdates?: MessageFE["progressUpdates"];
    thinkingContent?: string;
    isThinkingComplete?: boolean;
}

interface StoredTask {
    taskId: string;
    messageBubbles: StoredBubble[];
    taskMetadata?: unknown;
    createdTime: number;
}

// ============ Helpers ============

const ARTIFACT_RETURN_REGEX = /«artifact_return:([^»]+)»/g;
const ARTIFACT_REGEX = /«artifact:([^»]+)»/g;

function stripVersionSuffix(filename: string): string {
    if (filename.includes(":")) {
        const parts = filename.split(":");
        const lastPart = parts[parts.length - 1];
        if (/^\d+$/.test(lastPart)) {
            return parts.slice(0, -1).join(":");
        }
    }
    return filename;
}

function createArtifactPart(filename: string, sessionId: string) {
    const cleanFilename = stripVersionSuffix(filename);
    return {
        kind: "artifact" as const,
        status: "completed" as const,
        name: cleanFilename,
        file: {
            name: cleanFilename,
            uri: `artifact://${sessionId}/${cleanFilename}`,
        },
    };
}

/**
 * Extracts artifact markers from text and appends artifact parts to the output array.
 * Mutates `addedArtifacts` and `processedParts` for deduplication across multiple calls.
 */
function extractArtifactMarkers(text: string, sessionId: string, addedArtifacts: Set<string>, processedParts: PartFE[]): void {
    ARTIFACT_RETURN_REGEX.lastIndex = 0;
    ARTIFACT_REGEX.lastIndex = 0;

    let match;
    while ((match = ARTIFACT_RETURN_REGEX.exec(text)) !== null) {
        const artifactFilename = match[1];
        const normalizedFilename = artifactFilename.includes(":") && /:\d+$/.test(artifactFilename) ? artifactFilename.substring(0, artifactFilename.lastIndexOf(":")) : artifactFilename;

        if (!addedArtifacts.has(normalizedFilename)) {
            addedArtifacts.add(normalizedFilename);
            processedParts.push(createArtifactPart(artifactFilename, sessionId));
        }
    }

    while ((match = ARTIFACT_REGEX.exec(text)) !== null) {
        const artifactFilename = match[1];
        if (!addedArtifacts.has(artifactFilename)) {
            addedArtifacts.add(artifactFilename);
            processedParts.push(createArtifactPart(artifactFilename, sessionId));
        }
    }
}

// ============ Main ============

/**
 * Deserializes stored task data into MessageFE objects for rendering.
 * Handles artifact marker extraction, text cleanup, and message reconstruction.
 */
export function deserializeChatMessages(task: StoredTask, sessionId: string): MessageFE[] {
    return task.messageBubbles.map(bubble => {
        const processedParts: PartFE[] = [];
        const originalParts = bubble.parts ?? [{ kind: "text" as const, text: bubble.text ?? "" }];
        const addedArtifacts = new Set<string>();

        // Check bubble.text for artifact markers (TaskLoggerService saves markers there)
        if (bubble.text) {
            extractArtifactMarkers(bubble.text, sessionId, addedArtifacts, processedParts);
        }

        for (const part of originalParts) {
            if (part.kind === "text" && "text" in part && part.text) {
                let textContent = part.text as string;

                extractArtifactMarkers(textContent, sessionId, addedArtifacts, processedParts);

                // Remove artifact and status update markers from text
                textContent = textContent.replace(/«artifact_return:[^»]+»/g, "");
                textContent = textContent.replace(/«artifact:[^»]+»/g, "");
                textContent = textContent.replace(/«status_update:[^»]+»\n?/g, "");

                if (textContent.trim()) {
                    processedParts.push({ kind: "text", text: textContent });
                }
            } else if (part.kind === "artifact" && "name" in part) {
                const artifactName = part.name as string;
                if (artifactName && !addedArtifacts.has(artifactName)) {
                    addedArtifacts.add(artifactName);
                    processedParts.push(part);
                }
            } else {
                processedParts.push(part);
            }
        }

        return {
            taskId: task.taskId,
            createdTime: task.createdTime,
            role: bubble.type === "user" ? "user" : "agent",
            parts: processedParts,
            isUser: bubble.type === "user",
            isComplete: true,
            files: bubble.files,
            uploadedFiles: bubble.uploadedFiles,
            artifactNotification: bubble.artifactNotification,
            isError: bubble.isError,
            displayHtml: bubble.displayHtml,
            contextQuote: bubble.contextQuote,
            contextQuoteSourceId: bubble.contextQuoteSourceId,
            senderDisplayName: bubble.sender_display_name,
            senderEmail: bubble.sender_email,
            ...(bubble.progressUpdates && bubble.progressUpdates.length > 0 ? { progressUpdates: bubble.progressUpdates } : {}),
            ...((bubble.thinkingContent?.length ?? 0) > 0 ? { thinkingContent: bubble.thinkingContent, isThinkingComplete: bubble.isThinkingComplete ?? true } : {}),
            metadata: {
                messageId: bubble.id,
                sessionId,
                lastProcessedEventSequence: 0,
            },
        };
    });
}
