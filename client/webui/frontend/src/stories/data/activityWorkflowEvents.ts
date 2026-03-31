import type { A2AEventSSEPayload, TaskFE } from "@/lib/types";
import {
    BASE_TIME,
    offsetTime,
    makeEvent,
    makeTask,
    makeRequestEvent,
    makeSignalEvent,
    makeCompletedResponseEvent,
    makeFailedResponseEvent,
    makeStatusUpdateEvent,
} from "./a2aEventFactories";

// --- Scenario: Simple Tool Call ---

const simpleToolCallEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("What is the weather in San Francisco?", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "What is the weather in San Francisco?" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-weather-1",
                                name: "get_weather",
                                args: { city: "San Francisco" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1200)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-weather-1",
            tool_name: "get_weather",
            tool_args: { city: "San Francisco" },
        },
        "OrchestratorAgent",
        offsetTime(1300)
    ),
    makeSignalEvent(
        "tool_result",
        {
            function_call_id: "fc-weather-1",
            tool_name: "get_weather",
            result_data: { temperature: "68°F", condition: "Partly cloudy", humidity: "65%" },
        },
        "OrchestratorAgent",
        offsetTime(2000)
    ),
    makeStatusUpdateEvent("The weather in San Francisco is 68°F and partly cloudy with 65% humidity.", "OrchestratorAgent", offsetTime(2500)),
    makeCompletedResponseEvent("The weather in San Francisco is 68°F and partly cloudy with 65% humidity.", "OrchestratorAgent", offsetTime(3000)),
];

export const simpleToolCallTask = makeTask({
    taskId: "task-1",
    initialRequestText: "What is the weather in San Francisco?",
    events: simpleToolCallEvents,
    lastUpdated: new Date(offsetTime(3000)),
});

export const simpleToolCallMonitoredTasks: Record<string, TaskFE> = {
    "task-1": simpleToolCallTask,
};

// --- Scenario: Peer Delegation ---

const peerDelegationParentEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Validate order #5678 and check inventory", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Validate order #5678 and check inventory" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-validate-1",
                                name: "peer_ValidatorAgent",
                                args: { order_id: "5678" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-validate-1",
            tool_name: "peer_ValidatorAgent",
            tool_args: { order_id: "5678" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    makeSignalEvent(
        "tool_result",
        {
            function_call_id: "fc-validate-1",
            tool_name: "peer_ValidatorAgent",
            result_data: { is_valid: true, items: ["Widget A", "Widget B"] },
        },
        "OrchestratorAgent",
        offsetTime(3500)
    ),
    makeStatusUpdateEvent("Order #5678 is valid with 2 items: Widget A and Widget B.", "OrchestratorAgent", offsetTime(4000)),
    makeCompletedResponseEvent("Order #5678 has been validated. It contains Widget A and Widget B, both in stock.", "OrchestratorAgent", offsetTime(4500)),
];

const peerDelegationChildEvents: A2AEventSSEPayload[] = [
    makeEvent({
        direction: "request",
        timestamp: offsetTime(1200),
        task_id: "task-2",
        source_entity: "OrchestratorAgent",
        target_entity: "ValidatorAgent",
        payload_summary: { method: "message/send" },
        full_payload: {
            method: "message/send",
            params: {
                message: {
                    parts: [{ kind: "text", text: "Validate order #5678" }],
                    metadata: {
                        function_call_id: "fc-validate-1",
                        parentTaskId: "task-1",
                        agent_name: "ValidatorAgent",
                    },
                },
                metadata: {
                    function_call_id: "fc-validate-1",
                    parentTaskId: "task-1",
                },
            },
        },
    }),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Validate order #5678" }] }],
            },
        },
        "ValidatorAgent",
        offsetTime(1500),
        "task-2"
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [{ text: "Order #5678 is valid. It contains Widget A and Widget B." }],
                },
            },
        },
        "ValidatorAgent",
        offsetTime(2500),
        "task-2"
    ),
    makeCompletedResponseEvent("Order #5678 is valid.", "ValidatorAgent", offsetTime(3000), "task-2"),
];

const peerDelegationParentTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Validate order #5678 and check inventory",
    events: peerDelegationParentEvents,
    lastUpdated: new Date(offsetTime(4500)),
});

const peerDelegationChildTask = makeTask({
    taskId: "task-2",
    initialRequestText: "Validate order #5678",
    events: peerDelegationChildEvents,
    firstSeen: new Date(offsetTime(1200)),
    lastUpdated: new Date(offsetTime(3000)),
    parentTaskId: "task-1",
});

export const peerDelegationMonitoredTasks: Record<string, TaskFE> = {
    "task-1": peerDelegationParentTask,
    "task-2": peerDelegationChildTask,
};

// --- Scenario: Task Failed ---

const taskFailedEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Connect to the production database and fetch all user records", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Connect to the production database and fetch all user records" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-db-1",
                                name: "query_database",
                                args: { query: "SELECT * FROM users" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-db-1",
            tool_name: "query_database",
            tool_args: { query: "SELECT * FROM users" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    makeFailedResponseEvent("Connection timeout: Unable to reach production database at db.example.internal:5432. Please verify network connectivity and database availability.", "OrchestratorAgent", offsetTime(6000)),
];

export const taskFailedTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Connect to the production database and fetch all user records",
    events: taskFailedEvents,
    lastUpdated: new Date(offsetTime(6000)),
});

export const taskFailedMonitoredTasks: Record<string, TaskFE> = {
    "task-1": taskFailedTask,
};

// --- Scenario: Workflow Execution ---

const workflowEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Run the data processing pipeline on Q4 sales data", offsetTime(0)),
    makeSignalEvent(
        "workflow_execution_start",
        {
            workflow_name: "Data Processing Pipeline",
            execution_id: "exec-001",
            workflow_input: { dataset: "Q4 sales", format: "csv" },
        },
        "OrchestratorAgent",
        offsetTime(500)
    ),
    makeSignalEvent(
        "workflow_node_execution_start",
        {
            node_id: "validate-input",
            node_type: "agent",
            condition: "input.format in ['csv', 'json']",
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "workflow_node_execution_result",
        {
            node_id: "validate-input",
            status: "success",
            metadata: { condition: "input.format in ['csv', 'json']", condition_result: true },
        },
        "OrchestratorAgent",
        offsetTime(2000)
    ),
    makeSignalEvent(
        "workflow_node_execution_start",
        {
            node_id: "transform-data",
            node_type: "agent",
        },
        "OrchestratorAgent",
        offsetTime(2500)
    ),
    makeSignalEvent(
        "workflow_node_execution_result",
        {
            node_id: "transform-data",
            status: "success",
            metadata: { rows_processed: 15000, output_format: "parquet" },
        },
        "OrchestratorAgent",
        offsetTime(5000)
    ),
    makeSignalEvent(
        "workflow_execution_result",
        {
            status: "success",
            workflow_output: { rows_processed: 15000, output_path: "/data/output/q4_sales.parquet" },
        },
        "OrchestratorAgent",
        offsetTime(5500)
    ),
    makeCompletedResponseEvent("Pipeline completed successfully. Processed 15,000 rows of Q4 sales data.", "OrchestratorAgent", offsetTime(6000)),
];

export const workflowTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Run the data processing pipeline on Q4 sales data",
    events: workflowEvents,
    lastUpdated: new Date(offsetTime(6000)),
});

export const workflowMonitoredTasks: Record<string, TaskFE> = {
    "task-1": workflowTask,
};

// --- Scenario: In-Progress (Working) ---

const inProgressEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Analyze the customer feedback data and generate a sentiment report", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Analyze the customer feedback data and generate a sentiment report" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-analyze-1",
                                name: "analyze_sentiment",
                                args: { dataset: "customer_feedback" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-analyze-1",
            tool_name: "analyze_sentiment",
            tool_args: { dataset: "customer_feedback" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    // No completed/failed event — task is still in progress
];

export const inProgressTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Analyze the customer feedback data and generate a sentiment report",
    events: inProgressEvents,
    lastUpdated: new Date(offsetTime(1100)),
});

export const inProgressMonitoredTasks: Record<string, TaskFE> = {
    "task-1": inProgressTask,
};

// --- Scenario: Artifact Creation ---
// Covers: AGENT_ARTIFACT_NOTIFICATION via artifact_saved signal

const artifactCreationEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Generate a sales report PDF for Q4", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Generate a sales report PDF for Q4" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-report-1",
                                name: "generate_report",
                                args: { quarter: "Q4", format: "pdf" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-report-1",
            tool_name: "generate_report",
            tool_args: { quarter: "Q4", format: "pdf" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    makeSignalEvent(
        "tool_result",
        {
            function_call_id: "fc-report-1",
            tool_name: "generate_report",
            result_data: { status: "success", filename: "q4_sales_report.pdf" },
        },
        "OrchestratorAgent",
        offsetTime(3000)
    ),
    // artifact_saved without synthetic function_call_id → creates AGENT_ARTIFACT_NOTIFICATION immediately
    makeSignalEvent(
        "artifact_saved",
        {
            filename: "q4_sales_report.pdf",
            version: 1,
            description: "Q4 Sales Report with charts and regional breakdown",
            mime_type: "application/pdf",
            function_call_id: "fc-report-1",
        },
        "OrchestratorAgent",
        offsetTime(3200)
    ),
    makeStatusUpdateEvent("Here is your Q4 sales report.", "OrchestratorAgent", offsetTime(3500)),
    makeCompletedResponseEvent("Here is your Q4 sales report. I've generated a PDF with charts and regional breakdown.", "OrchestratorAgent", offsetTime(4000)),
];

export const artifactCreationTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Generate a sales report PDF for Q4",
    events: artifactCreationEvents,
    lastUpdated: new Date(offsetTime(4000)),
});

export const artifactCreationMonitoredTasks: Record<string, TaskFE> = {
    "task-1": artifactCreationTask,
};

// --- Scenario: Parallel Tool Calls ---
// Covers: AGENT_LLM_RESPONSE_TOOL_DECISION with isParallel, multiple AGENT_TOOL_INVOCATION_START/RESULT

const parallelToolCallEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Get the weather in New York and London simultaneously", offsetTime(0)),
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [{ role: "user", parts: [{ text: "Get the weather in New York and London simultaneously" }] }],
            },
        },
        "OrchestratorAgent",
        offsetTime(200)
    ),
    // LLM responds with two parallel function calls
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [
                        {
                            function_call: {
                                id: "fc-ny-1",
                                name: "get_weather",
                                args: { city: "New York" },
                            },
                        },
                        {
                            function_call: {
                                id: "fc-london-1",
                                name: "get_weather",
                                args: { city: "London" },
                            },
                        },
                    ],
                },
            },
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-ny-1",
            tool_name: "get_weather",
            tool_args: { city: "New York" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    makeSignalEvent(
        "tool_invocation_start",
        {
            function_call_id: "fc-london-1",
            tool_name: "get_weather",
            tool_args: { city: "London" },
        },
        "OrchestratorAgent",
        offsetTime(1100)
    ),
    makeSignalEvent(
        "tool_result",
        {
            function_call_id: "fc-ny-1",
            tool_name: "get_weather",
            result_data: { temperature: "45°F", condition: "Rainy" },
        },
        "OrchestratorAgent",
        offsetTime(1800)
    ),
    makeSignalEvent(
        "tool_result",
        {
            function_call_id: "fc-london-1",
            tool_name: "get_weather",
            result_data: { temperature: "50°F", condition: "Overcast" },
        },
        "OrchestratorAgent",
        offsetTime(2000)
    ),
    // Second LLM call after tool results
    makeSignalEvent(
        "llm_invocation",
        {
            request: {
                model: "claude-sonnet-4-6",
                contents: [
                    { role: "user", parts: [{ text: "Get the weather in New York and London simultaneously" }] },
                    { role: "model", parts: [{ function_call: { id: "fc-ny-1", name: "get_weather" } }, { function_call: { id: "fc-london-1", name: "get_weather" } }] },
                    { role: "tool", parts: [{ function_response: { name: "get_weather", response: { temperature: "45°F" } } }] },
                    { role: "tool", parts: [{ function_response: { name: "get_weather", response: { temperature: "50°F" } } }] },
                ],
            },
        },
        "OrchestratorAgent",
        offsetTime(2200)
    ),
    // LLM response to agent (text, not tool call) → AGENT_LLM_RESPONSE_TO_AGENT
    makeSignalEvent(
        "llm_response",
        {
            data: {
                content: {
                    parts: [{ text: "New York is 45°F and rainy. London is 50°F and overcast." }],
                },
                partial: false,
            },
        },
        "OrchestratorAgent",
        offsetTime(2800)
    ),
    makeStatusUpdateEvent("New York is 45°F and rainy. London is 50°F and overcast.", "OrchestratorAgent", offsetTime(3000)),
    makeCompletedResponseEvent("New York is 45°F and rainy. London is 50°F and overcast.", "OrchestratorAgent", offsetTime(3500)),
];

export const parallelToolCallTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Get the weather in New York and London simultaneously",
    events: parallelToolCallEvents,
    lastUpdated: new Date(offsetTime(3500)),
});

export const parallelToolCallMonitoredTasks: Record<string, TaskFE> = {
    "task-1": parallelToolCallTask,
};

// --- Scenario: Workflow with Map Progress and Agent Request ---
// Covers: WORKFLOW_MAP_PROGRESS, WORKFLOW_AGENT_REQUEST

const workflowMapEvents: A2AEventSSEPayload[] = [
    makeRequestEvent("Process all customer files through the review pipeline", offsetTime(0)),
    makeSignalEvent(
        "workflow_execution_start",
        {
            workflow_name: "Customer Review Pipeline",
            execution_id: "exec-map-001",
            workflow_input: { files: ["file1.csv", "file2.csv", "file3.csv"] },
        },
        "OrchestratorAgent",
        offsetTime(500)
    ),
    makeSignalEvent(
        "workflow_node_execution_start",
        {
            node_id: "review-agent",
            node_type: "agent",
            agent_name: "ReviewAgent",
        },
        "OrchestratorAgent",
        offsetTime(1000)
    ),
    makeSignalEvent(
        "workflow_map_progress",
        {
            node_id: "review-agent",
            total_items: 3,
            completed_items: 1,
            status: "in-progress",
        },
        "OrchestratorAgent",
        offsetTime(2000)
    ),
    makeSignalEvent(
        "workflow_map_progress",
        {
            node_id: "review-agent",
            total_items: 3,
            completed_items: 2,
            status: "in-progress",
        },
        "OrchestratorAgent",
        offsetTime(3000)
    ),
    makeSignalEvent(
        "workflow_map_progress",
        {
            node_id: "review-agent",
            total_items: 3,
            completed_items: 3,
            status: "completed",
        },
        "OrchestratorAgent",
        offsetTime(4000)
    ),
    makeSignalEvent(
        "workflow_node_execution_result",
        {
            node_id: "review-agent",
            status: "success",
            metadata: { items_processed: 3, all_passed: true },
        },
        "OrchestratorAgent",
        offsetTime(4500)
    ),
    makeSignalEvent(
        "workflow_execution_result",
        {
            status: "success",
            workflow_output: { total_reviewed: 3, passed: 3, failed: 0 },
        },
        "OrchestratorAgent",
        offsetTime(5000)
    ),
    makeCompletedResponseEvent("All 3 customer files reviewed successfully.", "OrchestratorAgent", offsetTime(5500)),
];

// Sub-task for workflow agent request
const workflowAgentRequestEvents: A2AEventSSEPayload[] = [
    makeEvent({
        direction: "request",
        timestamp: offsetTime(1100),
        task_id: "task-wf-agent-1",
        source_entity: "Workflow",
        target_entity: "ReviewAgent",
        payload_summary: { method: "message/send" },
        full_payload: {
            method: "message/send",
            params: {
                message: {
                    parts: [
                        { kind: "text", text: "Review customer file file1.csv" },
                        {
                            kind: "data",
                            data: {
                                type: "structured_invocation_request",
                                input_schema: { type: "object", properties: { filename: { type: "string" } } },
                                output_schema: { type: "object", properties: { passed: { type: "boolean" } } },
                            },
                        },
                    ],
                    metadata: {
                        workflow_name: "Customer Review Pipeline",
                        node_id: "review-agent",
                        parentTaskId: "task-1",
                        agent_name: "ReviewAgent",
                    },
                },
                metadata: {
                    parentTaskId: "task-1",
                },
            },
        },
    }),
    makeCompletedResponseEvent("Review complete. File passed.", "ReviewAgent", offsetTime(1900), "task-wf-agent-1"),
];

const workflowMapParentTask = makeTask({
    taskId: "task-1",
    initialRequestText: "Process all customer files through the review pipeline",
    events: workflowMapEvents,
    lastUpdated: new Date(offsetTime(5500)),
});

const workflowAgentSubTask = makeTask({
    taskId: "task-wf-agent-1",
    initialRequestText: "Review customer file file1.csv",
    events: workflowAgentRequestEvents,
    firstSeen: new Date(offsetTime(1100)),
    lastUpdated: new Date(offsetTime(1900)),
    parentTaskId: "task-1",
});

export const workflowMapMonitoredTasks: Record<string, TaskFE> = {
    "task-1": workflowMapParentTask,
    "task-wf-agent-1": workflowAgentSubTask,
};
