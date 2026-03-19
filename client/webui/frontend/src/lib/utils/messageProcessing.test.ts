import { describe, it, expect } from "vitest";
import type { Part, DataPart, TextPart } from "@/lib/types/be";
import type { MessageFE } from "@/lib/types/fe";
import { filterContentParts, checkHasVisibleContent, isCompactionNotificationBubble } from "./messageProcessing";

// --- helpers ---

function dataPart(type: string): DataPart {
    return { kind: "data", data: { type } } as DataPart;
}

function textPart(text: string): TextPart {
    return { kind: "text", text };
}

function filePart(): Part {
    return { kind: "file", file: { name: "test.txt", bytes: "" } } as Part;
}

function agentMessage(taskId: string, parts: Part[] = []): MessageFE {
    return { isUser: false, taskId, parts, role: "agent" } as MessageFE;
}

// --- filterContentParts ---

describe("filterContentParts", () => {
    it("keeps compaction_notification data parts", () => {
        const parts: Part[] = [dataPart("compaction_notification")];
        expect(filterContentParts(parts, false)).toEqual(parts);
    });

    it("keeps deep_research_progress data parts", () => {
        const parts: Part[] = [dataPart("deep_research_progress")];
        expect(filterContentParts(parts, false)).toEqual(parts);
    });

    it("filters out generic data parts", () => {
        const parts: Part[] = [dataPart("agent_progress")];
        expect(filterContentParts(parts, false)).toEqual([]);
    });

    it("keeps text parts when no deep research", () => {
        const parts: Part[] = [textPart("hello")];
        expect(filterContentParts(parts, false)).toEqual(parts);
    });

    it("filters text parts when deep research present", () => {
        const drp = dataPart("deep_research_progress");
        const parts: Part[] = [textPart("hello"), drp];
        expect(filterContentParts(parts, true)).toEqual([drp]);
    });

    it("keeps file parts always", () => {
        const parts: Part[] = [filePart()];
        expect(filterContentParts(parts, false)).toEqual(parts);
        expect(filterContentParts(parts, true)).toEqual(parts);
    });

    it("returns empty array for empty input", () => {
        expect(filterContentParts([], false)).toEqual([]);
    });

    it("handles mixed parts correctly", () => {
        const cn = dataPart("compaction_notification");
        const txt = textPart("response");
        const generic = dataPart("tool_result");
        const file = filePart();
        const result = filterContentParts([cn, txt, generic, file], false);
        expect(result).toEqual([cn, txt, file]);
    });
});

// --- checkHasVisibleContent ---

describe("checkHasVisibleContent", () => {
    it("returns true for compaction_notification", () => {
        expect(checkHasVisibleContent([dataPart("compaction_notification")], false)).toBe(true);
    });

    it("returns true for deep_research_progress", () => {
        expect(checkHasVisibleContent([dataPart("deep_research_progress")], false)).toBe(true);
    });

    it("returns true for non-empty text", () => {
        expect(checkHasVisibleContent([textPart("hello")], false)).toBe(true);
    });

    it("returns false for whitespace-only text", () => {
        expect(checkHasVisibleContent([textPart("   ")], false)).toBe(false);
    });

    it("returns true when isTaskFailed", () => {
        expect(checkHasVisibleContent([], true)).toBe(true);
    });

    it("returns true for file part", () => {
        expect(checkHasVisibleContent([filePart()], false)).toBe(true);
    });

    it("returns false for empty parts when not failed", () => {
        expect(checkHasVisibleContent([], false)).toBe(false);
    });

    it("returns false for generic data part only", () => {
        expect(checkHasVisibleContent([dataPart("tool_result")], false)).toBe(false);
    });
});

// --- isCompactionNotificationBubble ---

describe("isCompactionNotificationBubble", () => {
    const taskId = "task-123";

    it("returns true for agent msg, same taskId, single compaction part", () => {
        const msg = agentMessage(taskId);
        const parts: Part[] = [dataPart("compaction_notification")];
        expect(isCompactionNotificationBubble(msg, taskId, parts)).toBe(true);
    });

    it("returns false when last message is user", () => {
        const msg: MessageFE = { isUser: true, taskId, parts: [] } as MessageFE;
        const parts: Part[] = [dataPart("compaction_notification")];
        expect(isCompactionNotificationBubble(msg, taskId, parts)).toBe(false);
    });

    it("returns false when taskId differs", () => {
        const msg = agentMessage("other-task");
        const parts: Part[] = [dataPart("compaction_notification")];
        expect(isCompactionNotificationBubble(msg, taskId, parts)).toBe(false);
    });

    it("returns false when multiple parts", () => {
        const msg = agentMessage(taskId);
        const parts: Part[] = [textPart("hello"), dataPart("compaction_notification")];
        expect(isCompactionNotificationBubble(msg, taskId, parts)).toBe(false);
    });

    it("returns false when data type is not compaction_notification", () => {
        const msg = agentMessage(taskId);
        const parts: Part[] = [dataPart("deep_research_progress")];
        expect(isCompactionNotificationBubble(msg, taskId, parts)).toBe(false);
    });

    it("returns false when no last message", () => {
        const parts: Part[] = [dataPart("compaction_notification")];
        expect(isCompactionNotificationBubble(undefined, taskId, parts)).toBe(false);
    });

    it("returns false for empty parts", () => {
        const msg = agentMessage(taskId);
        expect(isCompactionNotificationBubble(msg, taskId, [])).toBe(false);
    });
});
