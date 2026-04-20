import { describe, it, expect } from "vitest";
import { deserializeChatMessages } from "@/lib/providers/chat";

// ============ Helpers ============

function makeTask(bubbles: Array<{ type: "user" | "agent"; [key: string]: unknown }>, taskId = "task-1") {
    return {
        taskId,
        messageBubbles: bubbles,
        createdTime: 1000,
    };
}

// ============ Tests ============

describe("deserializeChatMessages", () => {
    describe("basic deserialization", () => {
        it("deserializes a user bubble", () => {
            const result = deserializeChatMessages(makeTask([{ id: "msg-1", type: "user", text: "hello", parts: [{ kind: "text", text: "hello" }] }]), "session-1");

            expect(result).toHaveLength(1);
            expect(result[0].isUser).toBe(true);
            expect(result[0].role).toBe("user");
            expect(result[0].taskId).toBe("task-1");
            expect(result[0].isComplete).toBe(true);
            expect(result[0].metadata?.messageId).toBe("msg-1");
            expect(result[0].metadata?.sessionId).toBe("session-1");
        });

        it("deserializes an agent bubble", () => {
            const result = deserializeChatMessages(makeTask([{ id: "msg-2", type: "agent", parts: [{ kind: "text", text: "response" }] }]), "session-1");

            expect(result).toHaveLength(1);
            expect(result[0].isUser).toBe(false);
            expect(result[0].role).toBe("agent");
        });

        it("deserializes multiple bubbles in order", () => {
            const result = deserializeChatMessages(
                makeTask([
                    { type: "user", parts: [{ kind: "text", text: "q" }] },
                    { type: "agent", parts: [{ kind: "text", text: "a" }] },
                ]),
                "session-1"
            );

            expect(result).toHaveLength(2);
            expect(result[0].isUser).toBe(true);
            expect(result[1].isUser).toBe(false);
        });

        it("falls back to bubble.text when parts are missing", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", text: "fallback text" }]), "session-1");

            expect(result[0].parts).toContainEqual(expect.objectContaining({ kind: "text", text: "fallback text" }));
        });

        it("preserves createdTime from task", () => {
            const result = deserializeChatMessages(makeTask([{ type: "user", parts: [{ kind: "text", text: "hi" }] }]), "session-1");

            expect(result[0].createdTime).toBe(1000);
        });
    });

    describe("artifact marker extraction", () => {
        it("extracts artifact_return markers from text", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "Here is the file «artifact_return:report.pdf»" }],
                    },
                ]),
                "session-1"
            );

            const artifactPart = result[0].parts.find(p => p.kind === "artifact");
            expect(artifactPart).toBeDefined();
            expect(artifactPart).toMatchObject({
                kind: "artifact",
                status: "completed",
                name: "report.pdf",
            });
        });

        it("extracts artifact: markers from text", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "Created «artifact:data.csv»" }],
                    },
                ]),
                "session-1"
            );

            const artifactPart = result[0].parts.find(p => p.kind === "artifact");
            expect(artifactPart).toMatchObject({ name: "data.csv" });
        });

        it("strips version suffix from artifact filenames", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "«artifact_return:file.md:0»" }],
                    },
                ]),
                "session-1"
            );

            const artifactPart = result[0].parts.find(p => p.kind === "artifact");
            expect(artifactPart).toMatchObject({ name: "file.md" });
        });

        it("removes artifact markers from text content", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "Here is «artifact_return:file.txt» your file" }],
                    },
                ]),
                "session-1"
            );

            const textPart = result[0].parts.find(p => p.kind === "text");
            expect(textPart).toMatchObject({ text: "Here is  your file" });
        });

        it("removes status update markers from text", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "«status_update:processing»\nActual response" }],
                    },
                ]),
                "session-1"
            );

            const textPart = result[0].parts.find(p => p.kind === "text");
            expect(textPart).toMatchObject({ text: "Actual response" });
        });

        it("deduplicates artifacts from bubble.text and parts", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        text: "«artifact_return:file.txt»",
                        parts: [{ kind: "text", text: "«artifact_return:file.txt»" }],
                    },
                ]),
                "session-1"
            );

            const artifactParts = result[0].parts.filter(p => p.kind === "artifact");
            expect(artifactParts).toHaveLength(1);
        });

        it("extracts multiple different artifacts", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "«artifact_return:a.txt»«artifact_return:b.txt»" }],
                    },
                ]),
                "session-1"
            );

            const artifactParts = result[0].parts.filter(p => p.kind === "artifact");
            expect(artifactParts).toHaveLength(2);
        });

        it("builds correct artifact URI with session ID", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "«artifact_return:doc.pdf»" }],
                    },
                ]),
                "ses-42"
            );

            const artifactPart = result[0].parts.find(p => p.kind === "artifact");
            expect(artifactPart).toMatchObject({
                file: { uri: "artifact://ses-42/doc.pdf" },
            });
        });
    });

    describe("existing artifact parts", () => {
        it("keeps artifact parts that are not duplicates", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "artifact", name: "file.txt", status: "completed" }],
                    },
                ]),
                "session-1"
            );

            expect(result[0].parts).toHaveLength(1);
            expect(result[0].parts[0]).toMatchObject({ kind: "artifact", name: "file.txt" });
        });

        it("skips duplicate artifact parts already added from markers", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        text: "«artifact_return:file.txt»",
                        parts: [
                            { kind: "text", text: "response" },
                            { kind: "artifact", name: "file.txt", status: "completed" },
                        ],
                    },
                ]),
                "session-1"
            );

            const artifactParts = result[0].parts.filter(p => p.kind === "artifact");
            expect(artifactParts).toHaveLength(1);
        });
    });

    describe("non-text parts", () => {
        it("passes through file parts unchanged", () => {
            const filePart = { kind: "file" as const, file: { name: "img.png", bytes: "base64data" } };
            const result = deserializeChatMessages(makeTask([{ type: "agent", parts: [filePart] }]), "session-1");

            expect(result[0].parts).toContainEqual(filePart);
        });

        it("passes through data parts unchanged", () => {
            const dataPart = { kind: "data" as const, data: { type: "deep_research_progress" } };
            const result = deserializeChatMessages(makeTask([{ type: "agent", parts: [dataPart] }]), "session-1");

            expect(result[0].parts).toContainEqual(dataPart);
        });
    });

    describe("metadata preservation", () => {
        it("preserves displayHtml for user messages", () => {
            const result = deserializeChatMessages(makeTask([{ type: "user", displayHtml: "<b>@User</b> hello", parts: [{ kind: "text", text: "hello" }] }]), "session-1");

            expect(result[0].displayHtml).toBe("<b>@User</b> hello");
        });

        it("preserves contextQuote and contextQuoteSourceId", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "user",
                        contextQuote: "quoted text",
                        contextQuoteSourceId: "task-0",
                        parts: [{ kind: "text", text: "followup" }],
                    },
                ]),
                "session-1"
            );

            expect(result[0].contextQuote).toBe("quoted text");
            expect(result[0].contextQuoteSourceId).toBe("task-0");
        });

        it("preserves collaborative session sender info", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "user",
                        sender_display_name: "Alice",
                        sender_email: "alice@example.com",
                        parts: [{ kind: "text", text: "hi" }],
                    },
                ]),
                "session-1"
            );

            expect(result[0].senderDisplayName).toBe("Alice");
            expect(result[0].senderEmail).toBe("alice@example.com");
        });

        it("preserves isError flag", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", isError: true, parts: [{ kind: "text", text: "error" }] }]), "session-1");

            expect(result[0].isError).toBe(true);
        });

        it("includes progressUpdates when present", () => {
            const updates = [{ type: "status" as const, text: "Working", timestamp: 123 }];
            const result = deserializeChatMessages(makeTask([{ type: "agent", progressUpdates: updates, parts: [{ kind: "text", text: "done" }] }]), "session-1");

            expect(result[0].progressUpdates).toEqual(updates);
        });

        it("omits progressUpdates when empty", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", progressUpdates: [], parts: [{ kind: "text", text: "done" }] }]), "session-1");

            expect(result[0]).not.toHaveProperty("progressUpdates");
        });

        it("includes thinkingContent when present", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", thinkingContent: "reasoning...", isThinkingComplete: true, parts: [{ kind: "text", text: "answer" }] }]), "session-1");

            expect(result[0].thinkingContent).toBe("reasoning...");
            expect(result[0].isThinkingComplete).toBe(true);
        });

        it("defaults isThinkingComplete to true", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", thinkingContent: "thinking", parts: [{ kind: "text", text: "answer" }] }]), "session-1");

            expect(result[0].isThinkingComplete).toBe(true);
        });

        it("omits thinkingContent when empty", () => {
            const result = deserializeChatMessages(makeTask([{ type: "agent", thinkingContent: "", parts: [{ kind: "text", text: "answer" }] }]), "session-1");

            expect(result[0]).not.toHaveProperty("thinkingContent");
        });
    });

    describe("empty / edge cases", () => {
        it("returns empty array for task with no bubbles", () => {
            const result = deserializeChatMessages(makeTask([]), "session-1");
            expect(result).toEqual([]);
        });

        it("drops text parts that are only whitespace after marker removal", () => {
            const result = deserializeChatMessages(
                makeTask([
                    {
                        type: "agent",
                        parts: [{ kind: "text", text: "«artifact_return:file.txt»  " }],
                    },
                ]),
                "session-1"
            );

            const textParts = result[0].parts.filter(p => p.kind === "text");
            expect(textParts).toHaveLength(0);
        });
    });
});
