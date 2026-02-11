/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, beforeEach, afterEach, beforeAll, afterAll, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import * as matchers from "@testing-library/jest-dom/matchers";

import { SSEProvider, useSSESubscription } from "@/lib/providers/SSEProvider";
import type { SSEConnectionState } from "@/lib/contexts/SSEContext";
import { useSSEContext } from "@/lib/hooks/useSSEContext";

expect.extend(matchers);

// MSW server for API mocking
const server = setupServer();

// Mock EventSource
class MockEventSource {
    static instances: MockEventSource[] = [];

    url: string;
    withCredentials: boolean;
    readyState: number = 0; // CONNECTING
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;

    constructor(url: string, options?: { withCredentials?: boolean }) {
        this.url = url;
        this.withCredentials = options?.withCredentials ?? false;
        MockEventSource.instances.push(this);
    }

    close() {
        this.readyState = 2; // CLOSED
    }

    // Helper methods for testing
    simulateOpen() {
        this.readyState = 1; // OPEN
        this.onopen?.(new Event("open"));
    }

    simulateMessage(data: string) {
        this.onmessage?.(new MessageEvent("message", { data }));
    }

    simulateError() {
        this.onerror?.(new Event("error"));
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

beforeAll(() => server.listen());
afterAll(() => server.close());

beforeEach(() => {
    global.EventSource = MockEventSource as unknown as typeof EventSource;
    MockEventSource.clear();
    sessionStorage.clear();
    localStorage.clear();
    // Set up mock auth token - getApiBearerToken reads from localStorage
    localStorage.setItem("access_token", "mock-token");
    vi.clearAllMocks();
    server.resetHandlers();
});

afterEach(() => {
    global.EventSource = originalEventSource;
});

// Test components
function TestSubscriber({
    endpoint,
    taskId,
    onStateChange,
    onMessage,
    onTaskAlreadyCompleted,
}: {
    endpoint: string | null;
    taskId?: string;
    onStateChange?: (state: SSEConnectionState) => void;
    onMessage?: (event: MessageEvent) => void;
    onTaskAlreadyCompleted?: () => void;
}) {
    const { connectionState } = useSSESubscription({
        endpoint,
        taskId,
        onMessage,
        onTaskAlreadyCompleted,
    });

    // Call onStateChange whenever connectionState changes
    if (onStateChange) {
        onStateChange(connectionState);
    }

    return <div data-testid="connection-state">{connectionState}</div>;
}

function TestTaskRegistry({ onTasksChange }: { onTasksChange?: (tasks: ReturnType<typeof useSSEContext>["getTasks"]) => void }) {
    const { registerTask, unregisterTask, getTask, getTasks, getTasksByMetadata } = useSSEContext();

    return (
        <div>
            <button
                data-testid="register-task"
                onClick={() =>
                    registerTask({
                        taskId: "task-123",
                        sseUrl: "http://localhost/sse/task-123",
                        metadata: { projectId: "project-1" },
                    })
                }
            >
                Register Task
            </button>
            <button data-testid="unregister-task" onClick={() => unregisterTask("task-123")}>
                Unregister Task
            </button>
            <button data-testid="get-tasks" onClick={() => onTasksChange?.(getTasks)}>
                Get Tasks
            </button>
            <div data-testid="task-count">{getTasks().length}</div>
            <div data-testid="task-by-id">{getTask("task-123")?.taskId ?? "none"}</div>
            <div data-testid="tasks-by-metadata">{getTasksByMetadata("projectId", "project-1").length}</div>
        </div>
    );
}

describe("SSEProvider", () => {
    describe("useSSESubscription", () => {
        test("starts disconnected when endpoint is null", () => {
            render(
                <SSEProvider>
                    <TestSubscriber endpoint={null} />
                </SSEProvider>
            );

            expect(screen.getByTestId("connection-state")).toHaveTextContent("disconnected");
            expect(MockEventSource.instances).toHaveLength(0);
        });

        test("creates EventSource when endpoint is provided", async () => {
            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            const eventSource = MockEventSource.getLatest();
            expect(eventSource?.url).toContain("http://localhost/sse");
            expect(eventSource?.url).toContain("token=mock-token");
            expect(eventSource?.withCredentials).toBe(true);
        });

        test("transitions to connected state on open", async () => {
            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            act(() => {
                MockEventSource.getLatest()?.simulateOpen();
            });

            await waitFor(() => {
                expect(screen.getByTestId("connection-state")).toHaveTextContent("connected");
            });
        });

        test("calls onMessage callback when message received", async () => {
            const onMessage = vi.fn();

            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" onMessage={onMessage} />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            act(() => {
                MockEventSource.getLatest()?.simulateOpen();
            });

            act(() => {
                MockEventSource.getLatest()?.simulateMessage('{"type":"test","data":"hello"}');
            });

            expect(onMessage).toHaveBeenCalledTimes(1);
            expect(onMessage).toHaveBeenCalledWith(expect.objectContaining({ data: '{"type":"test","data":"hello"}' }));
        });

        test("closes EventSource when endpoint becomes null", async () => {
            const { rerender } = render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            const eventSource = MockEventSource.getLatest();

            rerender(
                <SSEProvider>
                    <TestSubscriber endpoint={null} />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(eventSource?.readyState).toBe(2); // CLOSED
            });
        });

        test("deduplicates connections for same endpoint", async () => {
            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" />
                    <TestSubscriber endpoint="http://localhost/sse" />
                </SSEProvider>
            );

            await waitFor(() => {
                // Should only have one EventSource instance despite two subscribers
                expect(MockEventSource.instances).toHaveLength(1);
            });
        });

        test("broadcasts messages to all subscribers on same endpoint", async () => {
            const onMessage1 = vi.fn();
            const onMessage2 = vi.fn();

            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" onMessage={onMessage1} />
                    <TestSubscriber endpoint="http://localhost/sse" onMessage={onMessage2} />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            act(() => {
                MockEventSource.getLatest()?.simulateOpen();
            });

            act(() => {
                MockEventSource.getLatest()?.simulateMessage('{"type":"broadcast"}');
            });

            expect(onMessage1).toHaveBeenCalledTimes(1);
            expect(onMessage2).toHaveBeenCalledTimes(1);
        });

        test("keeps connection open when one subscriber unmounts but another remains", async () => {
            // Use a stateful wrapper to control subscribers without remounting provider
            let setShowSecond: (show: boolean) => void = () => {};

            function TestWrapper() {
                const [showSecond, _setShowSecond] = React.useState(true);
                setShowSecond = _setShowSecond;
                return (
                    <>
                        <TestSubscriber endpoint="http://localhost/sse" />
                        {showSecond && <TestSubscriber endpoint="http://localhost/sse" />}
                    </>
                );
            }

            render(
                <SSEProvider>
                    <TestWrapper />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });

            const eventSource = MockEventSource.getLatest();

            // Remove one subscriber by changing state (keeps provider mounted)
            act(() => {
                setShowSecond(false);
            });

            // Connection should still be open (readyState 0 = CONNECTING, 1 = OPEN, 2 = CLOSED)
            expect(eventSource?.readyState).not.toBe(2);
        });
    });

    describe("Task Registry", () => {
        test("registers a task", async () => {
            const user = userEvent.setup();

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            expect(screen.getByTestId("task-count")).toHaveTextContent("0");

            await user.click(screen.getByTestId("register-task"));

            expect(screen.getByTestId("task-count")).toHaveTextContent("1");
            expect(screen.getByTestId("task-by-id")).toHaveTextContent("task-123");
        });

        test("unregisters a task", async () => {
            const user = userEvent.setup();

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await user.click(screen.getByTestId("register-task"));
            expect(screen.getByTestId("task-count")).toHaveTextContent("1");

            await user.click(screen.getByTestId("unregister-task"));
            expect(screen.getByTestId("task-count")).toHaveTextContent("0");
        });

        test("queries tasks by metadata", async () => {
            const user = userEvent.setup();

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await user.click(screen.getByTestId("register-task"));

            expect(screen.getByTestId("tasks-by-metadata")).toHaveTextContent("1");
        });

        test("persists tasks to sessionStorage", async () => {
            const user = userEvent.setup();

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await user.click(screen.getByTestId("register-task"));

            // Check sessionStorage
            const stored = sessionStorage.getItem("sam_sse_tasks");
            expect(stored).not.toBeNull();

            const parsed = JSON.parse(stored!);
            expect(parsed).toHaveLength(1);
            expect(parsed[0].taskId).toBe("task-123");
        });

        test("loads tasks from sessionStorage on mount", async () => {
            // Pre-populate sessionStorage
            sessionStorage.setItem(
                "sam_sse_tasks",
                JSON.stringify([
                    {
                        taskId: "persisted-task",
                        sseUrl: "http://localhost/sse/persisted",
                        metadata: {},
                        registeredAt: Date.now(),
                    },
                ])
            );

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("task-count")).toHaveTextContent("1");
            });
        });

        test("removes stale tasks on mount", async () => {
            // Pre-populate with a stale task (older than 1 hour)
            const staleTime = Date.now() - 2 * 60 * 60 * 1000; // 2 hours ago
            sessionStorage.setItem(
                "sam_sse_tasks",
                JSON.stringify([
                    {
                        taskId: "stale-task",
                        sseUrl: "http://localhost/sse/stale",
                        metadata: {},
                        registeredAt: staleTime,
                    },
                ])
            );

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("task-count")).toHaveTextContent("0");
            });
        });

        test("does not add duplicate tasks", async () => {
            const user = userEvent.setup();

            render(
                <SSEProvider>
                    <TestTaskRegistry />
                </SSEProvider>
            );

            await user.click(screen.getByTestId("register-task"));
            await user.click(screen.getByTestId("register-task"));

            expect(screen.getByTestId("task-count")).toHaveTextContent("1");
        });
    });

    describe("Status check on reconnect", () => {
        test("checks task status before connecting when taskId provided", async () => {
            let statusCheckCalled = false;

            // Setup MSW handler for task status - return running
            server.use(
                http.get("*/api/v1/tasks/task-123/status", () => {
                    statusCheckCalled = true;
                    return HttpResponse.json({ is_running: true });
                })
            );

            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" taskId="task-123" />
                </SSEProvider>
            );

            // Wait for the status check and then SSE connection
            await waitFor(() => {
                expect(statusCheckCalled).toBe(true);
            });

            // Should still create EventSource since task is running
            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });
        });

        test("calls onTaskAlreadyCompleted when task is not running", async () => {
            // Setup MSW handler for task status - return NOT running
            server.use(
                http.get("*/api/v1/tasks/completed-task/status", () => {
                    return HttpResponse.json({ is_running: false });
                })
            );

            const onTaskAlreadyCompleted = vi.fn();

            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" taskId="completed-task" onTaskAlreadyCompleted={onTaskAlreadyCompleted} />
                </SSEProvider>
            );

            // Wait for the callback to be called
            await waitFor(
                () => {
                    expect(onTaskAlreadyCompleted).toHaveBeenCalledTimes(1);
                },
                { timeout: 3000 }
            );

            // Should NOT create EventSource since task already completed
            expect(MockEventSource.instances).toHaveLength(0);
        });

        test("proceeds with SSE if status check fails", async () => {
            // Setup MSW handler to return error
            server.use(
                http.get("*/api/v1/tasks/task-123/status", () => {
                    return HttpResponse.error();
                })
            );

            render(
                <SSEProvider>
                    <TestSubscriber endpoint="http://localhost/sse" taskId="task-123" />
                </SSEProvider>
            );

            // Should still create EventSource despite status check failure
            await waitFor(() => {
                expect(MockEventSource.instances).toHaveLength(1);
            });
        });
    });

    describe("Error handling", () => {
        test("throws error when useSSESubscription used outside provider", () => {
            // Suppress console.error for this test
            const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

            expect(() => {
                render(<TestSubscriber endpoint="http://localhost/sse" />);
            }).toThrow("useSSESubscription must be used within SSEProvider");

            consoleSpy.mockRestore();
        });

        test("throws error when useSSEContext used outside provider", () => {
            const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

            expect(() => {
                render(<TestTaskRegistry />);
            }).toThrow("useSSEContext must be used within SSEProvider");

            consoleSpy.mockRestore();
        });
    });
});
