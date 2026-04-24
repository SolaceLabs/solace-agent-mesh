/**
 * Tests for useBackgroundTaskMonitor — batched polling, grace period, skip-active-session.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { api } from "@/lib/api";
import { useBackgroundTaskMonitor, selectTerminationCandidates } from "@/lib/hooks/useBackgroundTaskMonitor";
import type { BackgroundTaskState } from "@/lib/types/background-tasks";

type ApiResponse = Response | Record<string, unknown>;

function makeFullResponse(body: unknown, ok = true, status = 200): Response {
    return {
        ok,
        status,
        json: async () => body,
    } as unknown as Response;
}

function makeActiveTask(overrides: Partial<{ id: string; session_id: string | null; start_time: number; last_activity_time: number | null }> = {}) {
    return {
        id: "task-1",
        user_id: "user-1",
        parent_task_id: null,
        start_time: Date.now() - 60_000,
        end_time: null,
        status: "running",
        initial_request_text: null,
        execution_mode: "background",
        last_activity_time: Date.now(),
        background_execution_enabled: true,
        max_execution_time_ms: null,
        session_id: "session-a",
        ...overrides,
    };
}

function makeStatusResponse(overrides: Partial<{ status: string; end_time: number | null }> = {}) {
    return {
        task: {
            id: "task-1",
            user_id: "user-1",
            parent_task_id: null,
            start_time: Date.now() - 60_000,
            end_time: Date.now(),
            status: "completed",
            initial_request_text: null,
            execution_mode: "background",
            last_activity_time: Date.now(),
            background_execution_enabled: true,
            max_execution_time_ms: null,
            session_id: "session-a",
            ...overrides,
        },
        is_running: false,
        is_background: true,
        can_reconnect: false,
        error_message: null,
    };
}

describe("useBackgroundTaskMonitor", () => {
    let getSpy: ReturnType<typeof vi.spyOn>;
    let baseTime: number;

    beforeEach(() => {
        baseTime = 1_700_000_000_000;
        vi.useFakeTimers({ now: baseTime });
        localStorage.clear();
        getSpy = vi.spyOn(api.webui, "get");
    });

    afterEach(() => {
        getSpy.mockRestore();
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    // Helper: flush pending microtasks when using fake timers.
    async function flushAsync() {
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });
    }

    async function registerAndSettle(result: { current: ReturnType<typeof useBackgroundTaskMonitor> }, taskId: string, sessionId = "session-a") {
        act(() => {
            result.current.registerBackgroundTask(taskId, sessionId);
        });
        // Flush microtasks from the state update + localStorage-write effect.
        await flushAsync();
    }

    test("single batch call per tick — no /status calls while all tasks are still running", async () => {
        // Mount-effect fetch + every tick uses this response.
        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                return {
                    tasks: [makeActiveTask({ id: "task-1" }), makeActiveTask({ id: "task-2" })],
                    count: 2,
                };
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-a" }));

        await registerAndSettle(result, "task-1");
        await registerAndSettle(result, "task-2");

        getSpy.mockClear();

        // Advance by one poll interval.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10_000);
        });

        const calls = getSpy.mock.calls.map((c: unknown[]) => String(c[0]));
        const batchCalls = calls.filter((url: string) => url.includes("/tasks/background/active"));
        const statusCalls = calls.filter((url: string) => /\/tasks\/[^/]+\/status/.test(url));

        expect(batchCalls.length).toBe(1);
        expect(statusCalls.length).toBe(0);
    });

    test("task missing from batch response (past grace period) fires onTaskCompleted with session id", async () => {
        const onTaskCompleted = vi.fn();

        // First tick: task is in the active list. Second tick: gone.
        let tickCount = 0;
        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                tickCount += 1;
                if (tickCount === 1) {
                    return {
                        tasks: [makeActiveTask({ id: "task-1", session_id: "session-other" })],
                        count: 1,
                    };
                }
                return { tasks: [], count: 0 };
            }
            if (/\/tasks\/task-1\/status/.test(endpoint)) {
                return makeFullResponse(makeStatusResponse({ status: "completed" })) as unknown as ApiResponse;
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        // currentSessionId differs from the task's session so the skip guard does not fire.
        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-viewing", onTaskCompleted }));

        // Register the task well in the past so the grace period is already expired.
        act(() => {
            result.current.registerBackgroundTask("task-1", "session-other");
        });
        // Advance past one full poll interval. Mount fetch (tickCount=1) saw the task;
        // the scheduled interval tick (tickCount=2) finds it missing and fires completion.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(11_000);
        });
        // Flush microtasks for the follow-up /status call and state updates.
        await flushAsync();

        expect(onTaskCompleted).toHaveBeenCalledWith("task-1", "session-other");
        expect(result.current.backgroundTasks.find(t => t.taskId === "task-1")).toBeUndefined();
    });

    test("task on currently-viewed session is not treated as terminated even when missing from batch", async () => {
        const onTaskCompleted = vi.fn();
        const onTaskFailed = vi.fn();

        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                // Batch consistently omits this task — e.g., backend marked terminal.
                return { tasks: [], count: 0 };
            }
            if (/\/tasks\/.+\/status/.test(endpoint)) {
                throw new Error("/status should not be called for tasks on the currently-viewed session");
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-viewing", onTaskCompleted, onTaskFailed }));

        act(() => {
            result.current.registerBackgroundTask("task-on-active", "session-viewing");
        });
        // Advance past grace period so the terminal branch would otherwise engage.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10_000);
        });

        expect(onTaskCompleted).not.toHaveBeenCalled();
        expect(onTaskFailed).not.toHaveBeenCalled();
        expect(result.current.backgroundTasks.some(t => t.taskId === "task-on-active")).toBe(true);
    });

    test("task on currently-viewed session is polled once SSE has gone stale", async () => {
        const onTaskCompleted = vi.fn();

        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                return { tasks: [], count: 0 };
            }
            if (/\/tasks\/task-stale\/status/.test(endpoint)) {
                return makeFullResponse(makeStatusResponse({ status: "completed" })) as unknown as ApiResponse;
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-viewing", onTaskCompleted }));

        act(() => {
            result.current.registerBackgroundTask("task-stale", "session-viewing");
        });
        // Advance past SSE_STALE_MS (60s) so the skip-active-session guard no longer applies.
        // Polling should now treat the task as terminal and fire completion.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(70_000);
        });
        await flushAsync();

        expect(onTaskCompleted).toHaveBeenCalledWith("task-stale", "session-viewing");
        expect(result.current.backgroundTasks.find(t => t.taskId === "task-stale")).toBeUndefined();
    });

    test("task missing from batch but /status reports running is NOT treated as complete", async () => {
        const onTaskCompleted = vi.fn();
        const onTaskFailed = vi.fn();

        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                // Batch endpoint transiently misses the task.
                return { tasks: [], count: 0 };
            }
            if (/\/tasks\/task-1\/status/.test(endpoint)) {
                // But /status confirms the task is still running.
                return makeFullResponse({
                    task: {
                        id: "task-1",
                        user_id: "user-1",
                        parent_task_id: null,
                        start_time: Date.now() - 60_000,
                        end_time: null,
                        status: "running",
                        initial_request_text: null,
                        execution_mode: "background",
                        last_activity_time: Date.now(),
                        background_execution_enabled: true,
                        max_execution_time_ms: null,
                        session_id: "session-other",
                    },
                    is_running: true,
                    is_background: true,
                    can_reconnect: true,
                    error_message: null,
                }) as unknown as ApiResponse;
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        // Task is on a different session than the one the user is viewing so the
        // skip-active-session guard does not short-circuit the tick; this test
        // specifically exercises the is_running guard in handleTerminalTask.
        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-viewing", onTaskCompleted, onTaskFailed }));

        act(() => {
            result.current.registerBackgroundTask("task-1", "session-other");
        });
        // Past one full poll interval so the scheduled tick runs /status.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(11_000);
        });

        expect(onTaskCompleted).not.toHaveBeenCalled();
        expect(onTaskFailed).not.toHaveBeenCalled();
        expect(result.current.backgroundTasks.some(t => t.taskId === "task-1")).toBe(true);
    });

    describe("selectTerminationCandidates (pure function)", () => {
        const makeTrackedTask = (overrides: Partial<BackgroundTaskState> = {}): BackgroundTaskState => ({
            taskId: "task-1",
            sessionId: "session-other",
            lastEventTimestamp: 0,
            isBackground: true,
            startTime: 0,
            registeredAt: 0,
            ...overrides,
        });

        test("task within registration grace period is NOT returned", () => {
            const now = 2_000;
            const tracked = [makeTrackedTask({ taskId: "fresh", registeredAt: 0 })];
            const result = selectTerminationCandidates(tracked, new Set(), "active-session", now);
            expect(result).toHaveLength(0);
        });

        test("task past registration grace period AND missing from batch is returned", () => {
            const now = 10_000;
            const tracked = [makeTrackedTask({ taskId: "old", registeredAt: 0 })];
            const result = selectTerminationCandidates(tracked, new Set(), "active-session", now);
            expect(result.map(t => t.taskId)).toEqual(["old"]);
        });

        test("task present in the server's active set is NOT returned", () => {
            const now = 10_000;
            const tracked = [makeTrackedTask({ taskId: "in-batch", registeredAt: 0 })];
            const activeTaskIds = new Set(["in-batch"]);
            const result = selectTerminationCandidates(tracked, activeTaskIds, "active-session", now);
            expect(result).toHaveLength(0);
        });

        test("task on currently-viewed session with fresh SSE is NOT returned", () => {
            const now = 30_000;
            const tracked = [makeTrackedTask({ taskId: "same", sessionId: "active", registeredAt: 0, lastEventTimestamp: now - 5_000 })];
            const result = selectTerminationCandidates(tracked, new Set(), "active", now);
            expect(result).toHaveLength(0);
        });

        test("task on currently-viewed session with stale SSE IS returned", () => {
            const now = 120_000;
            const tracked = [makeTrackedTask({ taskId: "stale", sessionId: "active", registeredAt: 0, lastEventTimestamp: 0 })];
            const result = selectTerminationCandidates(tracked, new Set(), "active", now);
            expect(result.map(t => t.taskId)).toEqual(["stale"]);
        });
    });

    test("network error on batch request does NOT mark tasks complete", async () => {
        const onTaskCompleted = vi.fn();
        const onTaskFailed = vi.fn();

        // Mount fetch returns ok (empty) so the task can be registered cleanly; subsequent calls fail.
        let callIndex = 0;
        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                callIndex += 1;
                if (callIndex === 1) {
                    return { tasks: [], count: 0 };
                }
                throw new Error("network down");
            }
            if (/\/tasks\/.+\/status/.test(endpoint)) {
                throw new Error("status should not be called on batch failure");
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        // Task is on a different session so the skip-active-session guard does not
        // short-circuit before the failing fetch is exercised.
        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-viewing", onTaskCompleted, onTaskFailed }));

        act(() => {
            result.current.registerBackgroundTask("task-1", "session-other");
        });
        // Advance past one full poll interval so the interval tick runs and its
        // batch fetch fails. Grace period is already expired by this point.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(11_000);
        });

        expect(onTaskCompleted).not.toHaveBeenCalled();
        expect(onTaskFailed).not.toHaveBeenCalled();
        expect(result.current.backgroundTasks.some(t => t.taskId === "task-1")).toBe(true);
    });

    test("server-fetched tasks on mount preserve session_id", async () => {
        getSpy.mockImplementation(async (endpoint: string) => {
            if (endpoint.includes("/tasks/background/active")) {
                return {
                    tasks: [makeActiveTask({ id: "task-from-server", session_id: "session-zzz" })],
                    count: 1,
                };
            }
            throw new Error(`unexpected endpoint: ${endpoint}`);
        });

        const { result } = renderHook(() => useBackgroundTaskMonitor({ userId: "user-1", currentSessionId: "session-a" }));

        // Let the mount-effect fetch resolve and state update.
        await flushAsync();

        expect(result.current.backgroundTasks.length).toBeGreaterThan(0);
        const serverTask = result.current.backgroundTasks.find(t => t.taskId === "task-from-server");
        expect(serverTask).toBeDefined();
        expect(serverTask!.sessionId).toBe("session-zzz");

        // Session-scoped filter now matches this task.
        expect(result.current.getSessionBackgroundTasks("session-zzz")).toHaveLength(1);
    });
});
