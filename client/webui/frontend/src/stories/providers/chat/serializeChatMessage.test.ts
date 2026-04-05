import { describe, it, expect } from "vitest";

import type { MessageFE, ArtifactPart } from "@/lib/types";
import { serializeChatMessage } from "@/lib/providers/chat";

function makeMessage(overrides: Partial<MessageFE> = {}): MessageFE {
    return {
        role: "agent",
        isUser: false,
        parts: [],
        ...overrides,
    };
}

describe("serializeChatMessage", () => {
    it("serializes a basic user message", () => {
        const result = serializeChatMessage(
            makeMessage({
                isUser: true,
                parts: [{ kind: "text", text: "hello" }],
                metadata: { messageId: "msg-1" },
            })
        );

        expect(result.type).toBe("user");
        expect(result.text).toBe("hello");
        expect(result.id).toBe("msg-1");
    });

    it("serializes a basic agent message", () => {
        const result = serializeChatMessage(
            makeMessage({
                isUser: false,
                parts: [{ kind: "text", text: "response" }],
            })
        );

        expect(result.type).toBe("agent");
        expect(result.text).toBe("response");
    });

    it("concatenates multiple text parts", () => {
        const result = serializeChatMessage(
            makeMessage({
                parts: [
                    { kind: "text", text: "first " },
                    { kind: "text", text: "second" },
                ],
            })
        );

        expect(result.text).toBe("first second");
    });

    it("embeds artifact markers in text", () => {
        const result = serializeChatMessage(
            makeMessage({
                parts: [{ kind: "text", text: "Here is the file: " }, { kind: "artifact", status: "completed", name: "report.pdf" } as ArtifactPart],
            })
        );

        expect(result.text).toBe("Here is the file: «artifact_return:report.pdf»");
    });

    it("generates an id when messageId is missing", () => {
        const result = serializeChatMessage(makeMessage());

        expect(result.id).toMatch(/^msg-/);
    });

    it("preserves error flag", () => {
        const result = serializeChatMessage(makeMessage({ isError: true }));

        expect(result.isError).toBe(true);
    });

    it("maps uploadedFiles to name and type", () => {
        const file = new File(["content"], "doc.txt", { type: "text/plain" });
        const result = serializeChatMessage(makeMessage({ uploadedFiles: [file] }));

        expect(result.uploadedFiles).toEqual([{ name: "doc.txt", type: "text/plain" }]);
    });

    it("includes progressUpdates when present", () => {
        const updates = [{ type: "status" as const, text: "Working", timestamp: 123 }];
        const result = serializeChatMessage(makeMessage({ progressUpdates: updates }));

        expect(result.progressUpdates).toEqual(updates);
    });

    it("omits progressUpdates when empty", () => {
        const result = serializeChatMessage(makeMessage({ progressUpdates: [] }));

        expect(result).not.toHaveProperty("progressUpdates");
    });

    it("includes thinkingContent when present", () => {
        const result = serializeChatMessage(
            makeMessage({
                thinkingContent: "reasoning...",
                isThinkingComplete: true,
            })
        );

        expect(result.thinkingContent).toBe("reasoning...");
        expect(result.isThinkingComplete).toBe(true);
    });

    it("defaults isThinkingComplete to true when thinkingContent exists", () => {
        const result = serializeChatMessage(
            makeMessage({
                thinkingContent: "thinking",
            })
        );

        expect(result.isThinkingComplete).toBe(true);
    });

    it("omits thinkingContent when empty", () => {
        const result = serializeChatMessage(makeMessage({ thinkingContent: "" }));

        expect(result).not.toHaveProperty("thinkingContent");
    });

    it("preserves displayHtml and contextQuote fields", () => {
        const result = serializeChatMessage(
            makeMessage({
                displayHtml: "<b>hello</b>",
                contextQuote: "quoted text",
                contextQuoteSourceId: "task-1",
            })
        );

        expect(result.displayHtml).toBe("<b>hello</b>");
        expect(result.contextQuote).toBe("quoted text");
        expect(result.contextQuoteSourceId).toBe("task-1");
    });

    it("passes through parts array as-is", () => {
        const parts: MessageFE["parts"] = [{ kind: "text", text: "hi" }, { kind: "artifact", status: "completed", name: "f.txt" } as ArtifactPart];
        const result = serializeChatMessage(makeMessage({ parts }));

        expect(result.parts).toBe(parts);
    });
});
