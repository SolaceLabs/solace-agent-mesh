import type { Part, DataPart, TextPart } from "@/lib/types/be";
import type { MessageFE } from "@/lib/types/fe";

/**
 * Filters message parts to only renderable data parts and visible content.
 * Keeps: compaction_notification, deep_research_progress data parts, files, artifacts.
 * Keeps text parts only when there is no deep research progress.
 */
export function filterRenderableDataParts(parts: Part[], hasDeepResearchProgress: boolean): Part[] {
    return parts.filter(p => {
        // Keep deep_research_progress and compaction_notification data parts
        if (p.kind === "data") {
            const dataPart = p as DataPart;
            const dataType = dataPart.data && (dataPart.data as Record<string, unknown>).type;
            return dataType === "deep_research_progress" || dataType === "compaction_notification";
        }
        // Filter out text parts if we have deep research progress (to show progress-only)
        if (p.kind === "text" && hasDeepResearchProgress) {
            return false;
        }
        // Keep files and artifacts
        return true;
    });
}

/**
 * Determines whether filtered parts contain visible content worth creating a message bubble for.
 * Checks for non-empty text, files, or renderable data parts (deep_research_progress, compaction_notification).
 */
export function checkHasVisibleContent(parts: Part[]): boolean {
    return parts.some(
        p => (p.kind === "text" && (p as TextPart).text.trim()) || p.kind === "file" || (p.kind === "data" && (p as DataPart).data && ((p as DataPart).data.type === "deep_research_progress" || (p as DataPart).data.type === "compaction_notification"))
    );
}

/**
 * Returns true when a compaction notification should be rendered as its own separate bubble
 * rather than appended to an existing message. This prevents the CompactionNotification
 * component's early-return from hiding streamed response text.
 */
export function isCompactionNotificationBubble(lastMessage: MessageFE | undefined, taskId: string, newContentParts: Part[]): boolean {
    return !!lastMessage && !lastMessage.isUser && lastMessage.taskId === taskId && newContentParts.length === 1 && newContentParts[0].kind === "data" && (newContentParts[0] as DataPart).data?.type === "compaction_notification";
}
