/**
 * TypeScript types for Scheduled Tasks feature
 */

export type ScheduleType = "cron" | "interval" | "one_time";
export type ExecutionStatus = "pending" | "running" | "completed" | "failed" | "timeout" | "cancelled";

export interface MessagePart {
  type: "text" | "file";
  text?: string;
  uri?: string;
}

export interface NotificationChannel {
  type: "sse" | "webhook" | "email" | "broker_topic";
  config: Record<string, unknown>;
}

export interface NotificationConfig {
  channels: NotificationChannel[];
  on_success: boolean;
  on_failure: boolean;
  include_artifacts: boolean;
}

export interface ScheduledTask {
  id: string;
  name: string;
  description?: string;
  
  namespace: string;
  user_id?: string;
  created_by: string;
  
  schedule_type: ScheduleType;
  schedule_expression: string;
  timezone: string;
  
  target_agent_name: string;
  task_message: MessagePart[];
  task_metadata?: Record<string, unknown>;
  
  enabled: boolean;
  max_retries: number;
  retry_delay_seconds: number;
  timeout_seconds: number;
  
  notification_config?: NotificationConfig;
  
  created_at: number;
  updated_at: number;
  next_run_at?: number;
  last_run_at?: number;
}

export interface TaskExecution {
  id: string;
  scheduled_task_id: string;
  
  status: ExecutionStatus;
  a2a_task_id?: string;
  
  scheduled_for: number;
  started_at?: number;
  completed_at?: number;
  duration_ms?: number;
  
  result_summary?: {
    agent_response?: string;
    messages?: Array<{ role: string; text: string }>;
    artifacts?: Array<{ name?: string; uri?: string; type?: string }>;
    metadata?: Record<string, unknown>;
    task_status?: string;
    error_code?: number;
    error_data?: unknown;
  };
  error_message?: string;
  retry_count: number;
  
  artifacts?: string[];
  notifications_sent?: Array<{
    type: string;
    status: string;
    timestamp: number;
    error?: string;
  }>;
}

export interface ScheduledTaskListResponse {
  tasks: ScheduledTask[];
  total: number;
  skip: number;
  limit: number;
}

export interface ExecutionListResponse {
  executions: TaskExecution[];
  total: number;
  skip: number;
  limit: number;
}

export interface SchedulerStatus {
  instance_id: string;
  namespace: string;
  is_leader: boolean;
  active_tasks_count: number;
  running_executions_count: number;
  pending_results_count?: number;
  scheduler_running: boolean;
  leader_info?: {
    leader_id: string;
    leader_namespace: string;
    acquired_at: number;
    expires_at: number;
    heartbeat_at: number;
    is_expired: boolean;
    is_self: boolean;
  };
}

export interface CreateScheduledTaskRequest {
  name: string;
  description?: string;
  schedule_type: ScheduleType;
  schedule_expression: string;
  timezone?: string;
  target_agent_name: string;
  task_message: MessagePart[];
  task_metadata?: Record<string, unknown>;
  enabled?: boolean;
  max_retries?: number;
  retry_delay_seconds?: number;
  timeout_seconds?: number;
  notification_config?: NotificationConfig;
  user_level?: boolean;
}

export interface UpdateScheduledTaskRequest {
  name?: string;
  description?: string;
  schedule_type?: ScheduleType;
  schedule_expression?: string;
  timezone?: string;
  target_agent_name?: string;
  task_message?: MessagePart[];
  task_metadata?: Record<string, unknown>;
  enabled?: boolean;
  max_retries?: number;
  retry_delay_seconds?: number;
  timeout_seconds?: number;
  notification_config?: NotificationConfig;
}