/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { SSEProvider } from "@/lib/providers/SSEProvider";
import { useStartIndexing, useIndexingSSE } from "@/lib/hooks/useIndexingSSE";
import { useSSEContext } from "@/lib/hooks/useSSEContext";

expect.extend(matchers);

// Mock EventSource
class MockEventSource {
    static instances: MockEventSource[] = [];

    url: string;
    withCredentials: boolean;
    readyState: number = 0; // CONNECTING
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    private eventListeners: Map<string, EventListener[]> = new Map();

    constructor(url: string, options?: { withCredentials?: boolean }) {
        this.url = url;
        this.withCredentials = options?.withCredentials ?? false;
        MockEventSource.instances.push(this);
    }

    close() {
        this.readyState = 2; // CLOSED
    }

    addEventListener(type: string, listener: EventListener) {
        const listeners = this.eventListeners.get(type) || [];
        listeners.push(listener);
        this.eventListeners.set(type, listeners);
    }

    removeEventListener(type: string, listener: EventListener) {
        const listeners = this.eventListeners.get(type) || [];
        this.eventListeners.set(
            type,
            listeners.filter(l => l !== listener)
        );
    }

    // Helper methods for testing
    simulateOpen() {
        this.readyState = 1; // OPEN
        this.onopen?.(new Event("open"));
    }

    simulateCustomEvent(type: string, data: string) {
        const listeners = this.eventListeners.get(type) || [];
        const event = new MessageEvent(type, { data });
        listeners.forEach(listener => listener(event));
    }

    static clear() {
        MockEventSource.instances = [];
    }

    static getLatest(): MockEventSource | undefined {
        return MockEventSource.instances[MockEventSource.instances.length - 1];
    }
}

// Replace global EventSource with mock
const originalEventSource = global.EventSource;

beforeEach(() => {
    global.EventSource = MockEventSource as unknown as typeof EventSource;
    MockEventSource.clear();
    sessionStorage.clear();
    localStorage.clear();
    localStorage.setItem("access_token", "mock-token");
    vi.clearAllMocks();
});

afterEach(() => {
    global.EventSource = originalEventSource;
});

// ============================================================================
// Test Components
// ============================================================================

function TestStartIndexing({ metadataKey }: { metadataKey?: string }) {
    const startIndexing = useStartIndexing(metadataKey);
    const { getTasks } = useSSEContext();

    return (
        <div>
            <button data-testid="start" onClick={() => startIndexing("/api/v1/sse/subscribe/task-abc", "project-1", "upload")}>
                Start
            </button>
            <div data-testid="task-count">{getTasks().length}</div>
            <div data-testid="task-data">{JSON.stringify(getTasks())}</div>
        </div>
    );
}

function TestIndexingSSE({
    resourceId,
    metadataKey,
    onComplete,
    onError,
    onEvent,
}: {
    resourceId: string;
    metadataKey?: string;
    onComplete?: () => void;
    onError?: (error: string) => void;
    onEvent?: (event: { type: string; [key: string]: unknown }) => void;
}) {
    const { isIndexing, connectionState, latestEvent, startIndexing } = useIndexingSSE({
        resourceId,
        metadataKey,
        onComplete,
        onError,
        onEvent,
    });

    return (
        <div>
            <div data-testid="is-indexing">{String(isIndexing)}</div>
            <div data-testid="connection-state">{connectionState}</div>
            <div data-testid="latest-event">{latestEvent ? JSON.stringify(latestEvent) : "none"}</div>
            <button data-testid="start-indexing" onClick={() => startIndexing("/api/v1/sse/subscribe/task-xyz", resourceId, "upload")}>
                Start Indexing
            </button>
        </div>
    );
}

// ============================================================================
// Tests
// ============================================================================

describe("useStartIndexing", () => {
    test("extracts taskId from URL, stores sseUrl, and uses default metadataKey", async () => {
        const user = userEvent.setup();

        render(
            <SSEProvider>
                <TestStartIndexing />
            </SSEProvider>
        );

        await user.click(screen.getByTestId("start"));

        const tasks = JSON.parse(screen.getByTestId("task-data").textContent!);
        expect(tasks).toHaveLength(1);
        expect(tasks[0].taskId).toBe("task-abc");
        expect(tasks[0].sseUrl).toBe("/api/v1/sse/subscribe/task-abc");
        expect(tasks[0].metadata).toEqual({ resourceId: "project-1", operation: "upload" });
    });

    test("uses custom metadataKey when provided", async () => {
        const user = userEvent.setup();

        render(
            <SSEProvider>
                <TestStartIndexing metadataKey="projectId" />
            </SSEProvider>
        );

        await user.click(screen.getByTestId("start"));

        const tasks = JSON.parse(screen.getByTestId("task-data").textContent!);
        expect(tasks[0].metadata).toEqual({ projectId: "project-1", operation: "upload" });
    });
});

describe("useIndexingSSE", () => {
    test("calls onComplete and unregisters task on task_completed", async () => {
        const user = userEvent.setup();
        const onComplete = vi.fn();
        const onEvent = vi.fn();

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" onComplete={onComplete} onEvent={onEvent} />
            </SSEProvider>
        );

        expect(screen.getByTestId("is-indexing")).toHaveTextContent("false");

        await user.click(screen.getByTestId("start-indexing"));
        expect(screen.getByTestId("is-indexing")).toHaveTextContent("true");

        await waitFor(() => {
            expect(MockEventSource.instances).toHaveLength(1);
        });

        const eventSource = MockEventSource.getLatest()!;
        act(() => eventSource.simulateOpen());

        // Send a progress event, then complete
        act(() => eventSource.simulateCustomEvent("index_message", JSON.stringify({ type: "progress", percent: 50 })));
        expect(onEvent).toHaveBeenCalledWith({ type: "progress", percent: 50 });

        await waitFor(() => {
            expect(screen.getByTestId("latest-event")).toHaveTextContent('"type":"progress"');
        });

        act(() => eventSource.simulateCustomEvent("index_message", JSON.stringify({ type: "task_completed" })));

        expect(onComplete).toHaveBeenCalledTimes(1);
        await waitFor(() => {
            expect(screen.getByTestId("is-indexing")).toHaveTextContent("false");
            expect(screen.getByTestId("latest-event")).toHaveTextContent("none");
        });
    });

    test("calls onError with error string on conversion_failed", async () => {
        const user = userEvent.setup();
        const onError = vi.fn();
        const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" onError={onError} />
            </SSEProvider>
        );

        await user.click(screen.getByTestId("start-indexing"));
        await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

        const eventSource = MockEventSource.getLatest()!;
        act(() => eventSource.simulateOpen());
        act(() => eventSource.simulateCustomEvent("index_message", JSON.stringify({ type: "conversion_failed", error: "Failed to convert 'doc.pdf'" })));

        expect(onError).toHaveBeenCalledWith("Failed to convert 'doc.pdf'");
        await waitFor(() => expect(screen.getByTestId("is-indexing")).toHaveTextContent("false"));

        consoleSpy.mockRestore();
    });

    test("uses fallback error message when error field is not a string", async () => {
        const user = userEvent.setup();
        const onError = vi.fn();
        const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" onError={onError} />
            </SSEProvider>
        );

        await user.click(screen.getByTestId("start-indexing"));
        await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

        const eventSource = MockEventSource.getLatest()!;
        act(() => eventSource.simulateOpen());
        act(() => eventSource.simulateCustomEvent("index_message", JSON.stringify({ type: "indexing_failed", error: { code: 500 } })));

        expect(onError).toHaveBeenCalledWith("Indexing failed");

        consoleSpy.mockRestore();
    });

    test("handles malformed JSON without crashing", async () => {
        const user = userEvent.setup();
        const onEvent = vi.fn();
        const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" onEvent={onEvent} />
            </SSEProvider>
        );

        await user.click(screen.getByTestId("start-indexing"));
        await waitFor(() => expect(MockEventSource.instances).toHaveLength(1));

        const eventSource = MockEventSource.getLatest()!;
        act(() => eventSource.simulateOpen());
        act(() => eventSource.simulateCustomEvent("index_message", "not valid json{{{"));

        expect(onEvent).not.toHaveBeenCalled();
        // Hook remains functional — task still registered
        expect(screen.getByTestId("is-indexing")).toHaveTextContent("true");

        consoleSpy.mockRestore();
    });

    test("picks up existing task from sessionStorage on mount", async () => {
        sessionStorage.setItem(
            "sam_sse_tasks",
            JSON.stringify([
                {
                    taskId: "existing-task",
                    sseUrl: "/api/v1/sse/subscribe/existing-task",
                    metadata: { resourceId: "project-1", operation: "upload" },
                    registeredAt: Date.now(),
                },
            ])
        );

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" />
            </SSEProvider>
        );

        await waitFor(() => {
            expect(screen.getByTestId("is-indexing")).toHaveTextContent("true");
        });

        await waitFor(() => {
            expect(MockEventSource.instances).toHaveLength(1);
        });
    });

    test("ignores tasks registered under a different resourceId", () => {
        sessionStorage.setItem(
            "sam_sse_tasks",
            JSON.stringify([
                {
                    taskId: "other-task",
                    sseUrl: "/api/v1/sse/subscribe/other-task",
                    metadata: { resourceId: "project-2", operation: "upload" },
                    registeredAt: Date.now(),
                },
            ])
        );

        render(
            <SSEProvider>
                <TestIndexingSSE resourceId="project-1" />
            </SSEProvider>
        );

        expect(screen.getByTestId("is-indexing")).toHaveTextContent("false");
        expect(MockEventSource.instances).toHaveLength(0);
    });
});
