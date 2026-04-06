import { describe, it, expect } from "vitest";
import { transformApiTask, transformApiExecution, transformTaskToApi, transformUpdateToApi } from "@/lib/types/scheduled-tasks";
import type { ScheduledTask, TaskExecution, CreateScheduledTaskRequest, UpdateScheduledTaskRequest } from "@/lib/types/scheduled-tasks";

describe("transformApiTask", () => {
    it("transforms snake_case API task to camelCase", () => {
        const apiTask = {
            id: "task-1",
            name: "Daily Report",
            description: "Generates a daily report",
            namespace: "default",
            user_id: "user-1",
            created_by: "admin",
            schedule_type: "cron" as const,
            schedule_expression: "0 9 * * *",
            timezone: "UTC",
            target_agent_name: "report-agent",
            target_type: "agent" as const,
            task_message: [{ type: "text" as const, text: "Generate report" }],
            task_metadata: { key: "value" },
            enabled: true,
            status: "active" as const,
            max_retries: 3,
            retry_delay_seconds: 60,
            timeout_seconds: 300,
            source: "ui",
            consecutive_failure_count: 0,
            run_count: 10,
            created_at: 1700000000,
            updated_at: 1700001000,
            next_run_at: 1700002000,
            last_run_at: 1700000500,
        };

        const result: ScheduledTask = transformApiTask(apiTask);

        expect(result.id).toBe("task-1");
        expect(result.name).toBe("Daily Report");
        expect(result.userId).toBe("user-1");
        expect(result.createdBy).toBe("admin");
        expect(result.scheduleType).toBe("cron");
        expect(result.scheduleExpression).toBe("0 9 * * *");
        expect(result.targetAgentName).toBe("report-agent");
        expect(result.targetType).toBe("agent");
        expect(result.taskMessage).toEqual([{ type: "text", text: "Generate report" }]);
        expect(result.maxRetries).toBe(3);
        expect(result.retryDelaySeconds).toBe(60);
        expect(result.timeoutSeconds).toBe(300);
        expect(result.consecutiveFailureCount).toBe(0);
        expect(result.runCount).toBe(10);
        expect(result.createdAt).toBe(1700000000);
        expect(result.updatedAt).toBe(1700001000);
        expect(result.nextRunAt).toBe(1700002000);
        expect(result.lastRunAt).toBe(1700000500);
        expect(result.notificationConfig).toBeUndefined();
    });

    it("transforms notification_config when present", () => {
        const apiTask = {
            id: "task-2",
            name: "Task with notifications",
            namespace: "default",
            created_by: "admin",
            schedule_type: "cron" as const,
            schedule_expression: "0 9 * * *",
            timezone: "UTC",
            target_agent_name: "agent",
            target_type: "agent" as const,
            task_message: [],
            enabled: true,
            status: "active" as const,
            max_retries: 0,
            retry_delay_seconds: 0,
            timeout_seconds: 300,
            consecutive_failure_count: 0,
            run_count: 0,
            created_at: 1700000000,
            updated_at: 1700000000,
            notification_config: {
                channels: [{ type: "email" as const, config: { to: "user@example.com" } }],
                on_success: true,
                on_failure: false,
                include_artifacts: true,
            },
        };

        const result = transformApiTask(apiTask);

        expect(result.notificationConfig).toBeDefined();
        expect(result.notificationConfig!.onSuccess).toBe(true);
        expect(result.notificationConfig!.onFailure).toBe(false);
        expect(result.notificationConfig!.includeArtifacts).toBe(true);
        expect(result.notificationConfig!.channels).toHaveLength(1);
    });
});

describe("transformApiExecution", () => {
    it("transforms snake_case API execution to camelCase", () => {
        const apiExecution = {
            id: "exec-1",
            scheduled_task_id: "task-1",
            status: "completed" as const,
            a2a_task_id: "a2a-123",
            scheduled_for: 1700000000,
            started_at: 1700000001,
            completed_at: 1700000060,
            duration_ms: 59000,
            error_message: undefined,
            retry_count: 0,
        };

        const result: TaskExecution = transformApiExecution(apiExecution);

        expect(result.id).toBe("exec-1");
        expect(result.scheduledTaskId).toBe("task-1");
        expect(result.status).toBe("completed");
        expect(result.a2aTaskId).toBe("a2a-123");
        expect(result.scheduledFor).toBe(1700000000);
        expect(result.startedAt).toBe(1700000001);
        expect(result.completedAt).toBe(1700000060);
        expect(result.durationMs).toBe(59000);
        expect(result.retryCount).toBe(0);
        expect(result.resultSummary).toBeUndefined();
    });

    it("transforms result_summary when present", () => {
        const apiExecution = {
            id: "exec-2",
            scheduled_task_id: "task-1",
            status: "completed" as const,
            scheduled_for: 1700000000,
            retry_count: 0,
            result_summary: {
                agent_response: "Report generated",
                task_status: "done",
                error_code: undefined,
                error_data: undefined,
                messages: [{ role: "assistant", text: "Done" }],
                artifacts: [{ name: "report.pdf", uri: "/files/report.pdf", type: "file" }],
                metadata: { pages: 5 },
            },
        };

        const result = transformApiExecution(apiExecution);

        expect(result.resultSummary).toBeDefined();
        expect(result.resultSummary!.agentResponse).toBe("Report generated");
        expect(result.resultSummary!.taskStatus).toBe("done");
        expect(result.resultSummary!.messages).toHaveLength(1);
        expect(result.resultSummary!.artifacts).toHaveLength(1);
        expect(result.resultSummary!.metadata).toEqual({ pages: 5 });
    });
});

describe("transformTaskToApi", () => {
    it("transforms camelCase create request to snake_case", () => {
        const task: CreateScheduledTaskRequest = {
            name: "New Task",
            description: "A new task",
            scheduleType: "cron",
            scheduleExpression: "0 9 * * *",
            timezone: "UTC",
            targetAgentName: "my-agent",
            targetType: "agent",
            taskMessage: [{ type: "text", text: "Hello" }],
            enabled: true,
            maxRetries: 3,
            retryDelaySeconds: 60,
            timeoutSeconds: 300,
        };

        const result = transformTaskToApi(task);

        expect(result.name).toBe("New Task");
        expect(result.schedule_type).toBe("cron");
        expect(result.schedule_expression).toBe("0 9 * * *");
        expect(result.target_agent_name).toBe("my-agent");
        expect(result.target_type).toBe("agent");
        expect(result.task_message).toEqual([{ type: "text", text: "Hello" }]);
        expect(result.max_retries).toBe(3);
        expect(result.retry_delay_seconds).toBe(60);
        expect(result.timeout_seconds).toBe(300);
        expect(result.notification_config).toBeUndefined();
    });

    it("transforms notificationConfig when present", () => {
        const task: CreateScheduledTaskRequest = {
            name: "Task with notify",
            scheduleType: "interval",
            scheduleExpression: "1h",
            targetAgentName: "agent",
            taskMessage: [],
            notificationConfig: {
                channels: [{ type: "webhook", config: { url: "https://example.com" } }],
                onSuccess: true,
                onFailure: true,
                includeArtifacts: false,
            },
        };

        const result = transformTaskToApi(task);

        expect(result.notification_config).toBeDefined();
        const nc = result.notification_config as Record<string, unknown>;
        expect(nc.on_success).toBe(true);
        expect(nc.on_failure).toBe(true);
        expect(nc.include_artifacts).toBe(false);
        expect(nc.channels).toHaveLength(1);
    });
});

describe("transformUpdateToApi", () => {
    it("only includes defined fields", () => {
        const update: UpdateScheduledTaskRequest = {
            name: "Updated Name",
            enabled: false,
        };

        const result = transformUpdateToApi(update);

        expect(result.name).toBe("Updated Name");
        expect(result.enabled).toBe(false);
        // Undefined fields should not be present
        expect(result).not.toHaveProperty("description");
        expect(result).not.toHaveProperty("schedule_type");
        expect(result).not.toHaveProperty("schedule_expression");
        expect(result).not.toHaveProperty("target_agent_name");
        expect(result).not.toHaveProperty("task_message");
        expect(result).not.toHaveProperty("max_retries");
        expect(result).not.toHaveProperty("notification_config");
    });

    it("omits all keys when update is empty", () => {
        const update: UpdateScheduledTaskRequest = {};

        const result = transformUpdateToApi(update);

        expect(Object.keys(result)).toHaveLength(0);
    });
});
