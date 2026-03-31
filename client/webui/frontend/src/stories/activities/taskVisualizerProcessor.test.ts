import { describe, test, expect } from "vitest";

import { processTaskForVisualization } from "@/lib/components/activities/taskVisualizerProcessor";
import type { A2AEventSSEPayload, TaskFE } from "@/lib/types";

/**
 * Creates a minimal A2A event for testing purposes.
 */
function makeEvent(overrides: Partial<A2AEventSSEPayload> = {}): A2AEventSSEPayload {
    return {
        event_type: "a2a_message",
        timestamp: new Date().toISOString(),
        solace_topic: "test/topic",
        direction: "response",
        source_entity: "TestAgent",
        target_entity: "User",
        task_id: "task-1",
        payload_summary: {},
        full_payload: {},
        ...overrides,
    };
}

/**
 * Creates a minimal TaskFE for testing purposes.
 */
function makeTask(overrides: Partial<TaskFE> = {}): TaskFE {
    return {
        taskId: "task-1",
        initialRequestText: "Hello",
        events: [],
        firstSeen: new Date("2024-01-01T00:00:00.000Z"),
        lastUpdated: new Date("2024-01-01T00:00:01.000Z"),
        ...overrides,
    };
}

// -- Reusable event factories for common scenarios --

function makeRequestEvent(text: string, timestamp = "2024-01-01T00:00:00.000Z"): A2AEventSSEPayload {
    return makeEvent({
        direction: "request",
        timestamp,
        source_entity: "User",
        target_entity: "Orchestrator",
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

function makeCompletedResponseEvent(text: string, agent = "Orchestrator", timestamp = "2024-01-01T00:00:01.000Z"): A2AEventSSEPayload {
    return makeEvent({
        direction: "response",
        timestamp,
        source_entity: agent,
        target_entity: "User",
        full_payload: {
            result: {
                status: { state: "completed", message: { parts: [{ kind: "text", text }] } },
                metadata: { agent_name: agent },
            },
        },
    });
}

function makeFailedResponseEvent(errorMessage: string, agent = "Orchestrator", timestamp = "2024-01-01T00:00:01.000Z"): A2AEventSSEPayload {
    return makeEvent({
        direction: "response",
        timestamp,
        source_entity: agent,
        target_entity: "User",
        full_payload: {
            result: {
                status: { state: "failed", message: { parts: [{ kind: "text", text: errorMessage }] } },
                metadata: { agent_name: agent },
            },
        },
    });
}

function makeStatusUpdateEvent(text: string, agent = "Orchestrator", timestamp = "2024-01-01T00:00:00.500Z"): A2AEventSSEPayload {
    return makeEvent({
        direction: "status-update",
        timestamp,
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

describe("processTaskForVisualization", () => {
    // -- Null / empty input handling --

    test("returns null when parentTaskObject is null", () => {
        const result = processTaskForVisualization([], {}, null);
        expect(result).toBeNull();
    });

    test("returns empty steps when task has no events", () => {
        const task = makeTask({ events: [] });
        const result = processTaskForVisualization([], { "task-1": task }, task);
        expect(result).not.toBeNull();
        expect(result!.steps).toEqual([]);
        expect(result!.status).toBe("working");
    });

    // -- Core request → response flow --

    test("produces USER_REQUEST step from a request event", () => {
        const requestEvent = makeRequestEvent("What is the weather?");
        const task = makeTask({ events: [requestEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        const userRequestSteps = result!.steps.filter(s => s.type === "USER_REQUEST");
        expect(userRequestSteps).toHaveLength(1);
        expect(userRequestSteps[0].data.text).toBe("What is the weather?");
        expect(userRequestSteps[0].source).toBe("User");
    });

    test("produces TASK_COMPLETED step from a completed response", () => {
        const requestEvent = makeRequestEvent("Hello");
        const responseEvent = makeCompletedResponseEvent("Hi there!");
        const task = makeTask({ events: [requestEvent, responseEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        expect(result!.status).toBe("completed");

        const completedSteps = result!.steps.filter(s => s.type === "TASK_COMPLETED");
        expect(completedSteps).toHaveLength(1);
        expect(completedSteps[0].source).toBe("Orchestrator");
    });

    test("produces TASK_FAILED step from a failed response", () => {
        const requestEvent = makeRequestEvent("Do something impossible");
        const responseEvent = makeFailedResponseEvent("Something went wrong");
        const task = makeTask({ events: [requestEvent, responseEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        expect(result!.status).toBe("failed");

        const failedSteps = result!.steps.filter(s => s.type === "TASK_FAILED");
        expect(failedSteps).toHaveLength(1);
    });

    // -- Task-level metadata --

    test("calculates duration for completed tasks", () => {
        const requestEvent = makeRequestEvent("Hello", "2024-01-01T00:00:00.000Z");
        const responseEvent = makeCompletedResponseEvent("Done", "Orchestrator", "2024-01-01T00:00:05.000Z");
        const task = makeTask({ events: [requestEvent, responseEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        expect(result!.durationMs).toBe(5000);
        expect(result!.startTime).toBe("2024-01-01T00:00:00.000Z");
        expect(result!.endTime).toBe("2024-01-01T00:00:05.000Z");
    });

    test("status is 'working' when task has no terminal event", () => {
        const requestEvent = makeRequestEvent("Hello");
        const statusEvent = makeStatusUpdateEvent("Thinking...");
        const task = makeTask({ events: [requestEvent, statusEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        expect(result!.status).toBe("working");
        expect(result!.endTime).toBeUndefined();
        expect(result!.durationMs).toBeUndefined();
    });

    // -- Streaming text aggregation --

    test("aggregates streaming text into AGENT_RESPONSE_TEXT steps", () => {
        const requestEvent = makeRequestEvent("Hello");
        const textEvent1 = makeStatusUpdateEvent("Part 1 ", "Orchestrator", "2024-01-01T00:00:00.300Z");
        const textEvent2 = makeStatusUpdateEvent("Part 2", "Orchestrator", "2024-01-01T00:00:00.600Z");
        const responseEvent = makeCompletedResponseEvent("", "Orchestrator", "2024-01-01T00:00:01.000Z");

        const task = makeTask({ events: [requestEvent, textEvent1, textEvent2, responseEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        const textSteps = result!.steps.filter(s => s.type === "AGENT_RESPONSE_TEXT");
        expect(textSteps.length).toBeGreaterThanOrEqual(1);
    });

    // -- Synthetic request event --

    test("synthesizes a USER_REQUEST when no request event exists but initialRequestText is present", () => {
        const responseEvent = makeCompletedResponseEvent("Done", "Orchestrator", "2024-01-01T00:00:01.000Z");
        const task = makeTask({
            initialRequestText: "What is the weather?",
            events: [responseEvent],
        });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        expect(result).not.toBeNull();
        const userRequestSteps = result!.steps.filter(s => s.type === "USER_REQUEST");
        expect(userRequestSteps).toHaveLength(1);
        expect(userRequestSteps[0].data.text).toBe("What is the weather?");
    });

    test("does not mutate input parentTaskObject.events when synthesizing a request event", () => {
        const responseEvent = makeCompletedResponseEvent("Done", "Orchestrator", "2024-01-01T00:00:01.000Z");
        const task = makeTask({
            initialRequestText: "What is the weather?",
            events: [responseEvent],
        });
        const monitoredTasks: Record<string, TaskFE> = { "task-1": task };

        const originalEvents = task.events;
        const originalLength = task.events.length;
        const originalFirstEvent = task.events[0];

        processTaskForVisualization(task.events, monitoredTasks, task);

        expect(task.events).toBe(originalEvents);
        expect(task.events.length).toBe(originalLength);
        expect(task.events[0]).toBe(originalFirstEvent);
    });

    // -- Gateway timestamp stripping --

    test("strips gateway timestamp prefix from user request text", () => {
        const requestEvent = makeRequestEvent("Request received by gateway at: 2025-12-19T22:46:16.994017+00:00\nWhat is the weather?");
        const task = makeTask({ events: [requestEvent] });
        const result = processTaskForVisualization(task.events, { "task-1": task }, task);

        const userRequestSteps = result!.steps.filter(s => s.type === "USER_REQUEST");
        expect(userRequestSteps).toHaveLength(1);
        expect(userRequestSteps[0].data.text).toBe("What is the weather?");
    });

    // -- Sub-task / delegation --

    test("processes sub-task events with correct nesting level", () => {
        const requestEvent = makeRequestEvent("Research this topic");
        // Sub-task request with parentTaskId in message metadata for parent linkage
        // and function_call_id in params metadata for function call mapping
        const subTaskRequest = makeEvent({
            direction: "request",
            timestamp: "2024-01-01T00:00:00.200Z",
            task_id: "subtask-1",
            source_entity: "Orchestrator",
            target_entity: "ResearchAgent",
            payload_summary: { method: "message/send" },
            full_payload: {
                method: "message/send",
                params: {
                    message: {
                        parts: [{ kind: "text", text: "Please research" }],
                        metadata: { parentTaskId: "task-1" },
                    },
                    metadata: { function_call_id: "fc-1" },
                },
            },
        });
        const subTaskResponse = makeEvent({
            direction: "response",
            timestamp: "2024-01-01T00:00:00.800Z",
            task_id: "subtask-1",
            source_entity: "ResearchAgent",
            target_entity: "Orchestrator",
            full_payload: {
                result: {
                    status: { state: "completed", message: { parts: [{ kind: "text", text: "Research done" }] } },
                    metadata: { agent_name: "ResearchAgent" },
                },
            },
        });
        const responseEvent = makeCompletedResponseEvent("Here are the results", "Orchestrator", "2024-01-01T00:00:01.000Z");

        const subTask = makeTask({
            taskId: "subtask-1",
            initialRequestText: "Please research",
            events: [subTaskRequest, subTaskResponse],
            parentTaskId: "task-1",
        });
        const parentTask = makeTask({
            events: [requestEvent, responseEvent],
        });

        const monitoredTasks: Record<string, TaskFE> = {
            "task-1": parentTask,
            "subtask-1": subTask,
        };

        const result = processTaskForVisualization(parentTask.events, monitoredTasks, parentTask);
        expect(result).not.toBeNull();

        // Should have steps from both root task and sub-task
        const subTaskSteps = result!.steps.filter(s => s.nestingLevel > 0);
        expect(subTaskSteps.length).toBeGreaterThan(0);
    });

    // -- Idempotency --

    test("produces identical output when called multiple times with the same input", () => {
        const requestEvent = makeRequestEvent("Hello");
        const statusEvent = makeStatusUpdateEvent("Thinking...");
        const responseEvent = makeCompletedResponseEvent("Hi there!");
        const task = makeTask({ events: [requestEvent, statusEvent, responseEvent] });
        const monitoredTasks = { "task-1": task };

        const result1 = processTaskForVisualization(task.events, monitoredTasks, task);
        const result2 = processTaskForVisualization(task.events, monitoredTasks, task);

        expect(result1!.steps.length).toBe(result2!.steps.length);
        expect(result1!.status).toBe(result2!.status);
        expect(result1!.durationMs).toBe(result2!.durationMs);
        result1!.steps.forEach((step, i) => {
            expect(step.type).toBe(result2!.steps[i].type);
            expect(step.id).toBe(result2!.steps[i].id);
        });
    });
});
