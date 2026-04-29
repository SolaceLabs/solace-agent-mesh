import { describe, test, expect } from "vitest";
import { sessionKeys } from "@/lib/api/sessions/keys";

describe("sessionKeys", () => {
    test("all is the base key", () => {
        expect(sessionKeys.all).toEqual(["sessions"]);
    });

    test("lists() extends all with 'list'", () => {
        expect(sessionKeys.lists()).toEqual(["sessions", "list"]);
    });

    test("recent(userId, max) is scoped by userId", () => {
        expect(sessionKeys.recent("alice", 10)).toEqual(["sessions", "list", "recent", "alice", 10]);
    });

    test("infinite(userId, pageSize, source?) is scoped by userId", () => {
        expect(sessionKeys.infinite("alice", 20)).toEqual(["sessions", "list", "infinite", "alice", 20, undefined]);
        expect(sessionKeys.infinite("alice", 20, "scheduler")).toEqual(["sessions", "list", "infinite", "alice", 20, "scheduler"]);
    });

    test("different userId values produce non-equal recent keys", () => {
        expect(sessionKeys.recent("alice", 10)).not.toEqual(sessionKeys.recent("bob", 10));
    });

    test("different userId values produce non-equal infinite keys", () => {
        expect(sessionKeys.infinite("alice", 20)).not.toEqual(sessionKeys.infinite("bob", 20));
        expect(sessionKeys.infinite("alice", 20, "scheduler")).not.toEqual(sessionKeys.infinite("bob", 20, "scheduler"));
    });

    test("recent key starts with lists() prefix so prefix-invalidation matches", () => {
        const key = sessionKeys.recent("alice", 10);
        const prefix = sessionKeys.lists();
        expect(key.slice(0, prefix.length)).toEqual(prefix);
    });

    test("infinite key starts with lists() prefix so prefix-invalidation matches", () => {
        const key = sessionKeys.infinite("alice", 20, "scheduler");
        const prefix = sessionKeys.lists();
        expect(key.slice(0, prefix.length)).toEqual(prefix);
    });

    test("details() and detail(id) form the per-session key path", () => {
        expect(sessionKeys.details()).toEqual(["sessions", "detail"]);
        expect(sessionKeys.detail("sess-1")).toEqual(["sessions", "detail", "sess-1"]);
    });

    test("chatTasks(id) extends detail(id) with 'chat-tasks'", () => {
        expect(sessionKeys.chatTasks("sess-1")).toEqual(["sessions", "detail", "sess-1", "chat-tasks"]);
    });

    test("contextUsage(id, agentName?) extends detail(id) with 'context-usage' and agent slot", () => {
        expect(sessionKeys.contextUsage("sess-1")).toEqual(["sessions", "detail", "sess-1", "context-usage", null]);
        expect(sessionKeys.contextUsage("sess-1", "agent-x")).toEqual(["sessions", "detail", "sess-1", "context-usage", "agent-x"]);
    });
});
