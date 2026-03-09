import { v4 as uuidv4 } from "uuid";

import type { MessageFE, ArtifactPart, TextPart } from "@/lib/types";

const v4 = () => uuidv4({});

/**
 * Serializes a MessageFE into the format expected by the backend chat-tasks API.
 */
export function serializeChatMessage(message: MessageFE) {
    // Build text with artifact markers embedded
    let combinedText = "";
    const parts = message.parts || [];

    for (const part of parts) {
        if (part.kind === "text") {
            combinedText += (part as TextPart).text;
        } else if (part.kind === "artifact") {
            const artifactPart = part as ArtifactPart;
            combinedText += `«artifact_return:${artifactPart.name}»`;
        }
    }

    return {
        id: message.metadata?.messageId || `msg-${v4()}`,
        type: message.isUser ? "user" : "agent",
        text: combinedText,
        parts: message.parts,
        uploadedFiles: message.uploadedFiles?.map(f => ({
            name: f.name,
            type: f.type,
        })),
        isError: message.isError,
        displayHtml: message.displayHtml,
        contextQuote: message.contextQuote,
        contextQuoteSourceId: message.contextQuoteSourceId,
        // Persist inline progress timeline data so it survives page reloads
        ...(message.progressUpdates && message.progressUpdates.length > 0 ? { progressUpdates: message.progressUpdates } : {}),
        ...((message.thinkingContent?.length ?? 0) > 0 ? { thinkingContent: message.thinkingContent, isThinkingComplete: message.isThinkingComplete ?? true } : {}),
        // Persist HIL state so the summary banner survives page reloads.
        ...(message.userInputRequest ? { userInputRequest: message.userInputRequest } : {}),
    };
}
