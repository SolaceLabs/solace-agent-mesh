/**
 * Tests for normalizeSession — snake_case to camelCase normalization on the session critical path.
 */
import { describe, test, expect, vi, beforeEach } from "vitest";

const mockGet = vi.fn();
const mockPost = vi.fn();

describe("normalizeSession", () => {
    let service: typeof import("@/lib/api/sessions/service");

    beforeEach(async () => {
        vi.resetModules();
        mockGet.mockReset();
        mockPost.mockReset();

        vi.doMock("@/lib/api/client", () => ({
            api: {
                webui: {
                    get: mockGet,
                    post: mockPost,
                },
            },
        }));

        service = await import("@/lib/api/sessions/service");
    });

    test("normalizes snake_case-only input to camelCase", async () => {
        const snakeCaseSession = {
            id: "sess-1",
            name: "Test",
            agent_id: "agent-42",
            project_id: "proj-7",
            project_name: "My Project",
            created_time: "2025-01-01T00:00:00Z",
            updated_time: "2025-01-02T00:00:00Z",
            user_id: "user-99",
            has_running_background_task: true,
            owner_display_name: "Alice",
            owner_email: "alice@example.com",
        };

        mockGet.mockResolvedValue({ data: [snakeCaseSession], meta: { pagination: {} } });
        const sessions = await service.getRecentSessions(10);

        expect(sessions[0].agentId).toBe("agent-42");
        expect(sessions[0].projectId).toBe("proj-7");
        expect(sessions[0].projectName).toBe("My Project");
        expect(sessions[0].createdTime).toBe("2025-01-01T00:00:00Z");
        expect(sessions[0].updatedTime).toBe("2025-01-02T00:00:00Z");
        expect(sessions[0].userId).toBe("user-99");
        expect(sessions[0].hasRunningBackgroundTask).toBe(true);
        expect(sessions[0].ownerDisplayName).toBe("Alice");
        expect(sessions[0].ownerEmail).toBe("alice@example.com");
    });

    test("passes through camelCase-only input unchanged", async () => {
        const camelCaseSession = {
            id: "sess-2",
            name: "CamelTest",
            agentId: "agent-1",
            projectId: "proj-2",
            projectName: "Camel Project",
            createdTime: "2025-03-01T00:00:00Z",
            updatedTime: "2025-03-02T00:00:00Z",
            userId: "user-5",
            hasRunningBackgroundTask: false,
            ownerDisplayName: "Bob",
            ownerEmail: "bob@example.com",
        };

        mockGet.mockResolvedValue({ data: [camelCaseSession], meta: { pagination: {} } });
        const sessions = await service.getRecentSessions(10);

        expect(sessions[0].agentId).toBe("agent-1");
        expect(sessions[0].projectId).toBe("proj-2");
        expect(sessions[0].projectName).toBe("Camel Project");
        expect(sessions[0].createdTime).toBe("2025-03-01T00:00:00Z");
        expect(sessions[0].updatedTime).toBe("2025-03-02T00:00:00Z");
        expect(sessions[0].userId).toBe("user-5");
        expect(sessions[0].hasRunningBackgroundTask).toBe(false);
        expect(sessions[0].ownerDisplayName).toBe("Bob");
        expect(sessions[0].ownerEmail).toBe("bob@example.com");
    });

    test("prefers camelCase when both snake_case and camelCase are present", async () => {
        const mixedSession = {
            id: "sess-3",
            name: "Mixed",
            agentId: "camel-agent",
            agent_id: "snake-agent",
            createdTime: "2025-05-01T00:00:00Z",
            created_time: "2025-04-01T00:00:00Z",
        };

        mockGet.mockResolvedValue({ data: [mixedSession], meta: { pagination: {} } });
        const sessions = await service.getRecentSessions(10);

        expect(sessions[0].agentId).toBe("camel-agent");
        expect(sessions[0].createdTime).toBe("2025-05-01T00:00:00Z");
    });

    test("falls back to null/empty for missing fields", async () => {
        const minimalSession = {
            id: "sess-4",
            name: "Minimal",
        };

        mockGet.mockResolvedValue({ data: [minimalSession], meta: { pagination: {} } });
        const sessions = await service.getRecentSessions(10);

        expect(sessions[0].agentId).toBeNull();
        expect(sessions[0].projectId).toBeNull();
        expect(sessions[0].projectName).toBeNull();
        expect(sessions[0].createdTime).toBe("");
        expect(sessions[0].updatedTime).toBe("");
    });
});
