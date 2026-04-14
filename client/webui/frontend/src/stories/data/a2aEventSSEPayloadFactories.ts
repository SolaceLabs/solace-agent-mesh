import type { A2AEventSSEPayload, TaskFE } from "@/lib/types";

// Shared A2A event and task factory helpers used by both Storybook stories and unit tests.

export const BASE_TIME = "2024-06-15T10:00:00.000Z";

export function offsetTime(ms: number): string {
    return new Date(new Date(BASE_TIME).getTime() + ms).toISOString();
}

export function makeEvent(overrides: Partial<A2AEventSSEPayload> = {}): A2AEventSSEPayload {
    return {
        event_type: "a2a_message",
        timestamp: BASE_TIME,
        solace_topic: "test/topic",
        direction: "response",
        source_entity: "OrchestratorAgent",
        target_entity: "User",
        task_id: "task-1",
        payload_summary: {},
        full_payload: {},
        ...overrides,
    };
}

export function makeTask(overrides: Partial<TaskFE> = {}): TaskFE {
    return {
        taskId: "task-1",
        initialRequestText: "Hello",
        events: [],
        firstSeen: new Date(BASE_TIME),
        lastUpdated: new Date(BASE_TIME),
        ...overrides,
    };
}

export function makeRequestEvent(text: string, timestamp = BASE_TIME, taskId = "task-1"): A2AEventSSEPayload {
    return makeEvent({
        direction: "request",
        timestamp,
        task_id: taskId,
        source_entity: "User",
        target_entity: "OrchestratorAgent",
        payload_summary: { method: "message/send" },
        full_payload: {
            method: "message/send",
            params: {
                message: {
                    parts: [{ kind: "text", text }],
                },
            },
        },
    });
}

export function makeSignalEvent(signalType: string, signalData: Record<string, unknown>, agent: string, timestamp: string, taskId = "task-1"): A2AEventSSEPayload {
    return makeEvent({
        direction: "status-update",
        timestamp,
        task_id: taskId,
        source_entity: agent,
        full_payload: {
            result: {
                status: {
                    state: "working",
                    message: {
                        parts: [{ kind: "data", data: { type: signalType, ...signalData } }],
                        metadata: { agent_name: agent },
                    },
                },
                metadata: { agent_name: agent },
            },
        },
    });
}

export function makeCompletedResponseEvent(text: string, agent = "OrchestratorAgent", timestamp = BASE_TIME, taskId = "task-1"): A2AEventSSEPayload {
    return makeEvent({
        direction: "response",
        timestamp,
        task_id: taskId,
        source_entity: agent,
        target_entity: "User",
        full_payload: {
            result: {
                status: {
                    state: "completed",
                    message: { parts: [{ kind: "text", text }] },
                },
                metadata: { agent_name: agent },
            },
        },
    });
}

export function makeFailedResponseEvent(errorMessage: string, agent = "OrchestratorAgent", timestamp = BASE_TIME, taskId = "task-1"): A2AEventSSEPayload {
    return makeEvent({
        direction: "response",
        timestamp,
        task_id: taskId,
        source_entity: agent,
        target_entity: "User",
        full_payload: {
            result: {
                status: {
                    state: "failed",
                    message: { parts: [{ kind: "text", text: errorMessage }] },
                },
                metadata: { agent_name: agent },
            },
        },
    });
}

export function makeStatusUpdateEvent(text: string, agent = "OrchestratorAgent", timestamp = BASE_TIME, taskId = "task-1"): A2AEventSSEPayload {
    return makeEvent({
        direction: "status-update",
        timestamp,
        task_id: taskId,
        source_entity: agent,
        full_payload: {
            result: {
                status: {
                    state: "working",
                    message: {
                        parts: [{ kind: "text", text }],
                        metadata: { agent_name: agent },
                    },
                },
                metadata: { agent_name: agent },
            },
        },
    });
}
