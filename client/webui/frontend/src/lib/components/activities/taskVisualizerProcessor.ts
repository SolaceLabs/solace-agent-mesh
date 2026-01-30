/* eslint-disable @typescript-eslint/no-explicit-any */
import type {
    A2AEventSSEPayload,
    AgentPerformanceMetrics,
    Artifact,
    ArtifactNotificationData,
    DataPart,
    DelegationInfo,
    FilePart,
    JSONRPCError,
    LLMCallData,
    LLMResponseToAgentData,
    PerformanceReport,
    TaskFE,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
    ToolCallPerformance,
    ToolDecision,
    ToolDecisionData,
    ToolInvocationStartData,
    ToolResultData,
    VisualizerStep,
    VisualizerStepType,
    VisualizedTask,
} from "@/lib/types";

/**
 * Checks if an artifact is an intermediate web content artifact from deep research.
 * These are temporary files that should not be shown in the workflow visualization.
 *
 * @param artifactName The name of the artifact to check.
 * @returns True if the artifact is an intermediate web content artifact.
 */
const isIntermediateWebContentArtifact = (artifactName: string | undefined): boolean => {
    if (!artifactName) return false;
    // Skip web_content_ artifacts (temporary files from deep research)
    return artifactName.startsWith("web_content_");
};

/**
 * Helper function to get parentTaskId from a TaskFE object.
 * It first checks the direct `parentTaskId` field. If not present,
 * it attempts to infer it from the task's first event metadata.
 *
 * @param task The TaskFE object.
 * @returns The parentTaskId string, or null/undefined if not found.
 */
const getParentTaskIdFromTaskObject = (task: TaskFE): string | null | undefined => {
    // Infer from the first event if not set on the task object
    if (task.events && task.events.length > 0) {
        const firstEvent = task.events[0];
        // Typically, the first event for a sub-task is a 'request' event containing parentTaskId in its metadata
        if (firstEvent.full_payload?.params?.message?.metadata?.parentTaskId) {
            return firstEvent.full_payload.params.message.metadata.parentTaskId;
        }
    }
    return undefined;
};

const getEventTimestamp = (event: A2AEventSSEPayload): string => {
    return event.full_payload?.result?.status?.timestamp || event.timestamp;
};

/**
 * Recursively collects all events for a given task and all its descendant sub-tasks.
 * Also populates a map with the nesting level of each task.
 *
 * @param currentTaskId The ID of the task to start collecting from.
 * @param allMonitoredTasks A record of all monitored tasks.
 * @param taskNestingLevels A map to store the nesting level of each task ID.
 * @param currentLevel The current nesting level for currentTaskId.
 * @param visitedTaskIds A set of task IDs that have already been visited to prevent cycles/duplication.
 * @returns An array of A2AEventSSEPayload objects from the task and its descendants.
 */
const collectAllDescendantEvents = (currentTaskId: string, allMonitoredTasks: Record<string, TaskFE>, taskNestingLevels: Map<string, number>, currentLevel: number, visitedTaskIds: Set<string> = new Set()): A2AEventSSEPayload[] => {
    if (visitedTaskIds.has(currentTaskId)) {
        return [];
    }
    visitedTaskIds.add(currentTaskId);

    const task = allMonitoredTasks[currentTaskId];
    if (!task) {
        console.warn(`[collectAllDescendantEvents] Task not found in allMonitoredTasks: ${currentTaskId}`);
        return [];
    }

    taskNestingLevels.set(currentTaskId, currentLevel);
    let events: A2AEventSSEPayload[] = [...(task.events || [])];

    // Find and process direct children
    for (const taskIdInStore in allMonitoredTasks) {
        const potentialChildTask = allMonitoredTasks[taskIdInStore];
        if (potentialChildTask.taskId === currentTaskId) continue;

        // Use the helper to get parentTaskId, preferring the direct field but falling back to event inspection
        const childsParentId = getParentTaskIdFromTaskObject(potentialChildTask);

        if (childsParentId === currentTaskId) {
            events = events.concat(collectAllDescendantEvents(potentialChildTask.taskId, allMonitoredTasks, taskNestingLevels, currentLevel + 1, visitedTaskIds));
        }
    }
    return events;
};

/**
 * Processes raw A2A SSE events for a task and transforms them into a sequence of
 * logical visualizer steps, including duration calculations.
 *
 * @param _rawEventsForParentTask - An array of A2AEventSSEPayload objects for the primary task (now unused, events are fetched via parentTaskObject and collectAllDescendantEvents).
 * @param allMonitoredTasks - A record of all monitored tasks, used to find sub-task events.
 * @param parentTaskObject - The TaskFE object for the primary task being visualized.
 * @returns A VisualizedTask object containing all processed steps and task-level timing, or null if no data.
 */
export const processTaskForVisualization = (
    _rawEventsForParentTask: A2AEventSSEPayload[], // Parameter kept for signature compatibility, but not directly used for initial event set.
    allMonitoredTasks: Record<string, TaskFE>,
    parentTaskObject: TaskFE | null
): VisualizedTask | null => {
    if (!parentTaskObject) {
        return null;
    }

    // Check if there's a request event for the parent task
    const hasRequestEvent = parentTaskObject.events?.some(event => event.direction === "request" && event.task_id === parentTaskObject.taskId);

    // If no request event exists but we have initialRequestText, synthesize one
    // This handles the case where a background task is reconnected after browser refresh
    // and the original request event was not captured by the task logger
    if (!hasRequestEvent && parentTaskObject.initialRequestText && parentTaskObject.events && parentTaskObject.events.length > 0) {
        const firstEventTimestamp = parentTaskObject.events[0]?.timestamp || parentTaskObject.firstSeen.toISOString();
        // Create a synthetic timestamp slightly before the first event
        const syntheticTimestamp = new Date(new Date(firstEventTimestamp).getTime() - 1).toISOString();

        // Determine the target agent from the first event
        let targetAgent = "Orchestrator";
        const firstEvent = parentTaskObject.events[0];
        if (firstEvent?.source_entity) {
            targetAgent = firstEvent.source_entity;
        } else if (firstEvent?.full_payload?.result?.metadata?.agent_name) {
            targetAgent = firstEvent.full_payload.result.metadata.agent_name;
        }

        const syntheticRequestEvent: A2AEventSSEPayload = {
            task_id: parentTaskObject.taskId,
            direction: "request",
            timestamp: syntheticTimestamp,
            source_entity: "User",
            target_entity: targetAgent,
            event_type: "a2a_message",
            solace_topic: `synthetic/request/${parentTaskObject.taskId}`,
            payload_summary: {
                method: "message/send",
            },
            full_payload: {
                method: "message/send",
                params: {
                    message: {
                        parts: [
                            {
                                kind: "text",
                                text: parentTaskObject.initialRequestText,
                            },
                        ],
                    },
                },
            },
        };

        // Add the synthetic event to the beginning of the events array
        parentTaskObject.events = [syntheticRequestEvent, ...parentTaskObject.events];
    }

    // --- Performance Report Initialization ---
    const report: PerformanceReport = {
        overall: { totalTaskDurationMs: 0 },
        agents: {},
    };

    const inProgressLlmCalls = new Map<string, { timestamp: string; modelName: string }>(); // Key: agentInstanceId
    const inProgressToolCalls = new Map<
        string,
        {
            timestamp: string;
            toolName: string;
            isPeer: boolean;
            invokingAgentInstanceId: string;
            subTaskId?: string;
            parallelBlockId?: string;
        }
    >(); // Key: functionCallId

    const ensureAgentMetrics = (instanceId: string, agentName: string): AgentPerformanceMetrics => {
        if (!report.agents[instanceId]) {
            report.agents[instanceId] = {
                agentName,
                instanceId,
                displayName: agentName, // Temporary, will be updated in phase 2
                llmCalls: [],
                toolCalls: [],
                totalLlmTimeMs: 0,
                totalToolTimeMs: 0,
            };
        }
        return report.agents[instanceId];
    };
    // --- End Performance Report Initialization ---

    const taskNestingLevels = new Map<string, number>();

    // Queue for pending artifact completions that are waiting for their tool result
    // Key: function_call_id, Value: artifact data
    const pendingArtifacts = new Map<
        string,
        {
            filename: string;
            version?: number;
            description?: string;
            mimeType?: string;
            timestamp: string;
            agentName: string;
            taskId: string;
            nestingLevel: number;
            eventId: string;
        }
    >();

    const combinedEvents = collectAllDescendantEvents(
        parentTaskObject.taskId,
        allMonitoredTasks,
        taskNestingLevels,
        0, // Root task is at level 0
        new Set() // visitedTaskIds
    );

    if (combinedEvents.length === 0) {
        return {
            taskId: parentTaskObject.taskId,
            initialRequestText: parentTaskObject.initialRequestText,
            status: "working", // Or derive from parentTaskObject if it has a status
            startTime: parentTaskObject.firstSeen.toISOString(),
            steps: [],
        } as unknown as VisualizedTask;
    }

    // 2. Sort all collected events by timestamp
    const sortedEvents = combinedEvents.sort((a, b) => new Date(getEventTimestamp(a)).getTime() - new Date(getEventTimestamp(b)).getTime());

    const visualizerSteps: VisualizerStep[] = [];
    let lastStatusText: string | undefined = undefined;
    let currentAggregatedText = "";
    let aggregatedTextSourceAgent: string | undefined = undefined;
    let aggregatedTextTimestamp: string | undefined = undefined;
    let aggregatedRawEventIds: string[] = [];
    let lastFlushedAgentResponseText: string | null = null;
    let aggregatedTextIsForwardedContext: boolean | undefined = undefined;

    // State for duration calculation
    const subTaskToFunctionCallIdMap = new Map<string, string>();
    const functionCallIdToDelegationInfoMap = new Map<string, DelegationInfo>();
    const activeFunctionCallIdByTask = new Map<string, string>();
    const processedWorkflowEvents = new Set<string>();

    const flushAggregatedTextStep = (currentEventOwningTaskId?: string) => {
        if (currentAggregatedText.trim() && aggregatedTextSourceAgent && aggregatedTextTimestamp) {
            const textToFlush = currentAggregatedText.trim();

            let owningTaskIdForFlush = parentTaskObject.taskId;
            if (aggregatedRawEventIds.length > 0) {
                const parts = aggregatedRawEventIds[0].split("-");
                if (parts.length > 2 && parts[1] !== "global") {
                    owningTaskIdForFlush = parts.slice(1, parts.length - 1).join("-");
                }
            } else if (currentEventOwningTaskId) {
                owningTaskIdForFlush = currentEventOwningTaskId;
            }

            const nestingLevelForFlush = taskNestingLevels.get(owningTaskIdForFlush) ?? 0;
            const functionCallIdForStep = subTaskToFunctionCallIdMap.get(owningTaskIdForFlush) || activeFunctionCallIdByTask.get(owningTaskIdForFlush);

            const taskForFlush = allMonitoredTasks[owningTaskIdForFlush];
            const parentTaskIdForFlush = getParentTaskIdFromTaskObject(taskForFlush);

            visualizerSteps.push({
                id: `vstep-agenttext-${visualizerSteps.length}-${aggregatedRawEventIds[0] || "unknown"}`,
                type: "AGENT_RESPONSE_TEXT",
                timestamp: aggregatedTextTimestamp,
                title: `${aggregatedTextSourceAgent}: Response`,
                source: aggregatedTextSourceAgent,
                target: "User",
                data: { text: textToFlush },
                rawEventIds: [...aggregatedRawEventIds],
                isSubTaskStep: nestingLevelForFlush > 0,
                nestingLevel: nestingLevelForFlush,
                owningTaskId: owningTaskIdForFlush,
                parentTaskId: parentTaskIdForFlush || undefined,
                functionCallId: functionCallIdForStep,
            });
            lastFlushedAgentResponseText = textToFlush;
        }
        currentAggregatedText = "";
        aggregatedTextSourceAgent = undefined;
        aggregatedTextTimestamp = undefined;
        aggregatedRawEventIds = [];
        aggregatedTextIsForwardedContext = undefined;
    };

    // 3. Process the sorted, combined event stream
    sortedEvents.forEach((event, index) => {
        const eventTimestamp = getEventTimestamp(event);
        const eventId = `raw-${event.task_id || "global"}-${index}`;
        const payload = event.full_payload;
        const currentEventOwningTaskId = event.task_id || parentTaskObject.taskId;
        const currentEventNestingLevel = taskNestingLevels.get(currentEventOwningTaskId) ?? 0;

        const currentTask = allMonitoredTasks[currentEventOwningTaskId];
        const parentTaskId = getParentTaskIdFromTaskObject(currentTask);

        // Determine agent name
        let eventAgentName = event.source_entity || "UnknownAgent";
        if (payload?.params?.message?.metadata?.agent_name) {
            eventAgentName = payload.params.message.metadata.agent_name;
        } else if (payload?.result?.metadata?.agent_name) {
            eventAgentName = payload.result.metadata.agent_name;
        } else if (payload?.result?.status?.message?.metadata?.agent_name) {
            eventAgentName = payload.result.status.message.metadata.agent_name;
        } else if (payload?.result?.artifact?.metadata?.agent_name) {
            eventAgentName = payload.result.artifact.metadata.agent_name;
        }

        // Determine functionCallId for the step
        let functionCallIdForStep: string | undefined;
        // const metadataFunctionCallId = (payload?.result?.status?.message?.metadata as any)?.function_call_id;

        if (currentEventNestingLevel > 0) {
            functionCallIdForStep = subTaskToFunctionCallIdMap.get(currentEventOwningTaskId);
        } else {
            functionCallIdForStep = activeFunctionCallIdByTask.get(currentEventOwningTaskId);
        }

        // if (metadataFunctionCallId) {
        //     functionCallIdForStep = metadataFunctionCallId;
        // }

        // Handle sub-task creation requests to establish the mapping early
        if (event.direction === "request" && currentEventNestingLevel > 0) {
            // Note: metadata can be at params level (for tool delegation) or message level (for workflow agent calls)
            const paramsMetadata = payload.params?.metadata as any;
            const messageMetadata = payload.params?.message?.metadata as any;
            const functionCallId = paramsMetadata?.function_call_id || messageMetadata?.function_call_id;
            const subTaskId = event.task_id;

            if (subTaskId && functionCallId) {
                subTaskToFunctionCallIdMap.set(subTaskId, functionCallId);
                // This event's only purpose is to create the mapping.
                // It doesn't create a visual step itself, so we return.
                return;
            }

            // Check if this is a workflow agent request (has workflow_name in message metadata)
            const workflowName = messageMetadata?.workflow_name;
            const nodeId = messageMetadata?.node_id;
            if (workflowName && nodeId) {
                // This is a workflow agent invocation - create a WORKFLOW_AGENT_REQUEST step
                const params = payload.params as any;
                let inputText: string | undefined;
                let instruction: string | undefined;
                let inputArtifactRef: { name: string; version?: number; uri?: string; mimeType?: string } | undefined;
                let inputSchema: Record<string, any> | undefined;
                let outputSchema: Record<string, any> | undefined;
                let suggestedOutputFilename: string | undefined;

                if (params?.message?.parts) {
                    // Extract structured_invocation_request data part
                    const structuredInvocationPart = params.message.parts.find((p: any) => p.kind === "data" && p.data?.type === "structured_invocation_request");
                    if (structuredInvocationPart) {
                        const invocationData = structuredInvocationPart.data;
                        inputSchema = invocationData.input_schema;
                        outputSchema = invocationData.output_schema;
                        suggestedOutputFilename = invocationData.suggested_output_filename;
                    }

                    // Extract text parts (skip the reminder text)
                    // The first non-reminder text part is the instruction if present
                    const textParts = params.message.parts.filter((p: any) => p.kind === "text" && p.text && !p.text.includes("REMINDER:"));
                    if (textParts.length > 0) {
                        // First text part is the instruction
                        instruction = textParts[0].text;
                    }

                    // Extract file parts (artifact references) - this is the structured input
                    const fileParts = params.message.parts.filter((p: any) => p.kind === "file" && p.file);
                    if (fileParts.length > 0) {
                        const file = fileParts[0].file;
                        inputArtifactRef = {
                            name: file.name || "input",
                            version: file.version,
                            uri: file.uri,
                            mimeType: file.mimeType,
                        };
                    }

                    // If no file part but text parts exist after instruction, that's the inputText
                    // (for simple text schemas where input is sent as text, not artifact)
                    if (!inputArtifactRef && textParts.length > 1) {
                        inputText = textParts[1].text;
                    } else if (!inputArtifactRef && textParts.length === 1 && !instruction) {
                        // Single text part that's not instruction - it's the input
                        inputText = textParts[0].text;
                    }
                }

                const stepData = {
                    id: `vstep-wfagentreq-${visualizerSteps.length}-${eventId}`,
                    type: "WORKFLOW_AGENT_REQUEST" as const,
                    timestamp: eventTimestamp,
                    title: `Workflow Request to ${event.target_entity || eventAgentName}`,
                    source: "Workflow",
                    target: event.target_entity || eventAgentName,
                    data: {
                        workflowAgentRequest: {
                            agentName: event.target_entity || eventAgentName || "Unknown",
                            nodeId,
                            workflowName,
                            inputText,
                            inputArtifactRef,
                            instruction,
                            inputSchema,
                            outputSchema,
                            suggestedOutputFilename,
                        },
                    },
                    rawEventIds: [eventId],
                    isSubTaskStep: true,
                    nestingLevel: currentEventNestingLevel,
                    owningTaskId: currentEventOwningTaskId,
                    parentTaskId: parentTaskId || undefined,
                };
                visualizerSteps.push(stepData);
                return;
            }
        }

        // Skip rendering of cancel requests as not enough information is present yet to link to original task
        const isCancellationRequest = event.payload_summary.method && event.payload_summary.method === "tasks/cancel";
        if (isCancellationRequest) return;

        // USER REQUEST (for root task only)
        if (event.direction === "request" && currentEventNestingLevel === 0 && event.task_id === parentTaskObject.taskId) {
            flushAggregatedTextStep(currentEventOwningTaskId);
            lastFlushedAgentResponseText = null;
            const params = payload.params as any;
            let userText = "User request";
            if (params?.message?.parts) {
                const textParts = params.message.parts.filter((p: any) => p.kind === "text" && p.text);
                // Filter out gateway timestamp parts (they appear like "Request received by gateway at: 2025-12-19T22:46:16.994017+00:00")
                // The gateway prepends this as the first part, so we can skip parts that match this pattern
                const gatewayTimestampPattern = /^Request received by gateway at:/;
                const filteredParts = textParts.filter((p: any) => !gatewayTimestampPattern.test(p.text.trim()));
                if (filteredParts.length > 0) {
                    // Join remaining text parts
                    userText = filteredParts.map((p: any) => p.text).join("\n");
                } else if (textParts.length > 0) {
                    // Fallback: if all parts were filtered, use the last part but strip the gateway prefix
                    const lastPart = textParts[textParts.length - 1].text;
                    // Try to extract text after the timestamp line
                    const lines = lastPart.split("\n");
                    const nonGatewayLines = lines.filter((line: string) => !gatewayTimestampPattern.test(line.trim()));
                    userText = nonGatewayLines.length > 0 ? nonGatewayLines.join("\n") : lastPart;
                }
            }
            visualizerSteps.push({
                id: `vstep-userreq-${visualizerSteps.length}-${eventId}`,
                type: "USER_REQUEST",
                timestamp: eventTimestamp,
                title: "User Input",
                source: "User",
                target: event.target_entity || eventAgentName,
                data: { text: userText },
                rawEventIds: [eventId],
                isSubTaskStep: false,
                nestingLevel: 0,
                owningTaskId: currentEventOwningTaskId,
            });
            return;
        }

        // Any status_update with a result
        if (event.direction === "status-update" && payload?.result) {
            const result = payload.result as TaskStatusUpdateEvent;
            const statusMessage = result.status?.message;
            const messageMetadata = statusMessage?.metadata as any;

            let statusUpdateAgentName: string;
            // Check both message metadata and result metadata for forwarding flag
            const isForwardedMessage = !!messageMetadata?.forwarded_from_peer || !!result.metadata?.forwarded_from_peer;

            if (isForwardedMessage) {
                statusUpdateAgentName = messageMetadata?.forwarded_from_peer || result.metadata?.forwarded_from_peer;
            } else if (result.metadata?.agent_name) {
                statusUpdateAgentName = result.metadata.agent_name as string;
            } else if (messageMetadata?.agent_name) {
                statusUpdateAgentName = messageMetadata.agent_name as string;
            } else {
                statusUpdateAgentName = event.source_entity || "Agent";
            }
            const agentInstanceId = `${statusUpdateAgentName}:${currentEventOwningTaskId}`;

            // Only process the parts if this is an original event, not a forwarded one.
            if (!isForwardedMessage && statusMessage?.parts) {
                for (const part of statusMessage.parts) {
                    if (part.kind === "data") {
                        const data = part.data as any;
                        if (data.type === "agent_progress_update") {
                            lastStatusText = data.status_text;
                        } else if (data.type === "artifact_creation_progress") {
                            lastStatusText = `Saving artifact: ${data.filename} (${data.bytes_transferred} bytes)`;
                        }
                    }
                    if (part.kind === "data") {
                        flushAggregatedTextStep(currentEventOwningTaskId);
                        const dataPart = part as DataPart;
                        const signalData = dataPart.data as any;
                        const signalType = signalData?.type as string;

                        switch (signalType) {
                            case "workflow_execution_start": {
                                const dedupKey = `start:${signalData.execution_id}`;

                                if (processedWorkflowEvents.has(dedupKey)) {
                                    break;
                                }
                                processedWorkflowEvents.add(dedupKey);

                                const stepId = `vstep-wfstart-${visualizerSteps.length}-${eventId}`;
                                visualizerSteps.push({
                                    id: stepId,
                                    type: "WORKFLOW_EXECUTION_START",
                                    timestamp: eventTimestamp,
                                    title: `Workflow Started: ${signalData.workflow_name}`,
                                    source: "System",
                                    target: "Workflow",
                                    data: {
                                        workflowExecutionStart: {
                                            workflowName: signalData.workflow_name,
                                            executionId: signalData.execution_id,
                                            inputArtifactRef: signalData.input_artifact_ref,
                                            workflowInput: signalData.workflow_input,
                                        },
                                    },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    parentTaskId: parentTaskId || undefined,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "workflow_node_execution_start": {
                                const dedupKey = `node_start:${currentEventOwningTaskId}:${signalData.sub_task_id || signalData.node_id}:${signalData.iteration_index || 0}`;
                                if (processedWorkflowEvents.has(dedupKey)) break;
                                processedWorkflowEvents.add(dedupKey);

                                visualizerSteps.push({
                                    id: `vstep-wfnode-start-${visualizerSteps.length}-${eventId}`,
                                    type: "WORKFLOW_NODE_EXECUTION_START",
                                    timestamp: eventTimestamp,
                                    title: `Node Started: ${signalData.node_id} (${signalData.node_type})`,
                                    source: "Workflow",
                                    target: signalData.agent_name || signalData.node_id,
                                    data: {
                                        workflowNodeExecutionStart: {
                                            nodeId: signalData.node_id,
                                            nodeType: signalData.node_type,
                                            agentName: signalData.agent_name,
                                            inputArtifactRef: signalData.input_artifact_ref,
                                            iterationIndex: signalData.iteration_index,
                                            // Conditional node fields
                                            condition: signalData.condition,
                                            trueBranch: signalData.true_branch,
                                            falseBranch: signalData.false_branch,
                                            trueBranchLabel: signalData.true_branch_label,
                                            falseBranchLabel: signalData.false_branch_label,
                                            // Switch node fields
                                            cases: signalData.cases,
                                            defaultBranch: signalData.default_branch,
                                            // Join node fields
                                            waitFor: signalData.wait_for,
                                            joinStrategy: signalData.join_strategy,
                                            joinN: signalData.join_n,
                                            // Loop node fields
                                            maxIterations: signalData.max_iterations,
                                            loopDelay: signalData.loop_delay,
                                            // Common fields
                                            subTaskId: signalData.sub_task_id,
                                            parentNodeId: signalData.parent_node_id,
                                            // Parallel grouping
                                            parallelGroupId: signalData.parallel_group_id,
                                        },
                                    },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "workflow_node_execution_result": {
                                const dedupKey = `node_result:${currentEventOwningTaskId}:${signalData.node_id}:${signalData.status}`;
                                if (processedWorkflowEvents.has(dedupKey)) break;
                                processedWorkflowEvents.add(dedupKey);

                                visualizerSteps.push({
                                    id: `vstep-wfnode-result-${visualizerSteps.length}-${eventId}`,
                                    type: "WORKFLOW_NODE_EXECUTION_RESULT",
                                    timestamp: eventTimestamp,
                                    title: `Node Completed: ${signalData.node_id} (${signalData.status})`,
                                    source: signalData.node_id,
                                    target: "Workflow",
                                    data: {
                                        workflowNodeExecutionResult: {
                                            nodeId: signalData.node_id,
                                            status: signalData.status,
                                            outputArtifactRef: signalData.output_artifact_ref,
                                            errorMessage: signalData.error_message,
                                            metadata: signalData.metadata,
                                            conditionResult: signalData.metadata?.condition_result,
                                        },
                                    },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "workflow_map_progress": {
                                visualizerSteps.push({
                                    id: `vstep-wfmap-${visualizerSteps.length}-${eventId}`,
                                    type: "WORKFLOW_MAP_PROGRESS",
                                    timestamp: eventTimestamp,
                                    title: `Map Progress: ${signalData.node_id} (${signalData.completed_items}/${signalData.total_items})`,
                                    source: signalData.node_id,
                                    target: "Workflow",
                                    data: {
                                        workflowMapProgress: {
                                            nodeId: signalData.node_id,
                                            totalItems: signalData.total_items,
                                            completedItems: signalData.completed_items,
                                            status: signalData.status,
                                        },
                                    },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "workflow_execution_result": {
                                const dedupKey = `result:${currentEventOwningTaskId}:${signalData.status}`;
                                if (processedWorkflowEvents.has(dedupKey)) break;
                                processedWorkflowEvents.add(dedupKey);

                                visualizerSteps.push({
                                    id: `vstep-wfresult-${visualizerSteps.length}-${eventId}`,
                                    type: "WORKFLOW_EXECUTION_RESULT",
                                    timestamp: eventTimestamp,
                                    title: `Workflow Finished: ${signalData.status}`,
                                    source: "Workflow",
                                    target: "User",
                                    data: {
                                        workflowExecutionResult: {
                                            status: signalData.status,
                                            outputArtifactRef: signalData.output_artifact_ref,
                                            errorMessage: signalData.error_message,
                                            workflowOutput: signalData.workflow_output,
                                        },
                                    },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "agent_progress_update": {
                                visualizerSteps.push({
                                    id: `vstep-progress-${visualizerSteps.length}-${eventId}`,
                                    type: "AGENT_RESPONSE_TEXT",
                                    timestamp: eventTimestamp,
                                    title: `${statusUpdateAgentName}: Progress Update`,
                                    source: statusUpdateAgentName,
                                    target: "User",
                                    data: { text: signalData.status_text },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "llm_invocation": {
                                const llmData = signalData.request as any;
                                let promptText = "System-initiated LLM call";
                                if (llmData?.contents && Array.isArray(llmData.contents) && llmData.contents.length > 0) {
                                    // Get the last message in the conversation to understand what triggered this LLM call
                                    const lastContent = llmData.contents[llmData.contents.length - 1];
                                    const lastRole = lastContent?.role;

                                    // Check if this LLM call is following tool results
                                    // Tool results can be: role="tool", role="function", or parts with function_response
                                    const toolResultContents = llmData.contents.filter((c: any) => c.role === "tool" || c.role === "function" || (c.parts && c.parts.some((p: any) => p.function_response)));
                                    const hasToolResults = toolResultContents.length > 0;

                                    if (hasToolResults && lastRole !== "user") {
                                        // This is a follow-up LLM call after tool execution
                                        // Count only the tool results from the CURRENT turn, not the entire conversation history
                                        // Find the index of the last "model" role message (the LLM's response that called tools)
                                        let lastModelIndex = -1;
                                        for (let i = llmData.contents.length - 1; i >= 0; i--) {
                                            if (llmData.contents[i].role === "model") {
                                                lastModelIndex = i;
                                                break;
                                            }
                                        }

                                        // Count function_response parts that come AFTER the last model message
                                        // Also collect summaries of the tool results
                                        let actualToolResultCount = 0;
                                        const toolResultSummaries: string[] = [];
                                        const startIndex = lastModelIndex + 1;
                                        for (let i = startIndex; i < llmData.contents.length; i++) {
                                            const content = llmData.contents[i];
                                            if (content.parts && Array.isArray(content.parts)) {
                                                for (const part of content.parts) {
                                                    if (part.function_response) {
                                                        actualToolResultCount++;
                                                        const toolName = part.function_response.name || "unknown";
                                                        const response = part.function_response.response;
                                                        // Create a brief summary of the response
                                                        let summary: string;
                                                        if (typeof response === "string") {
                                                            summary = response.substring(0, 200);
                                                        } else if (typeof response === "object" && response !== null) {
                                                            const jsonStr = JSON.stringify(response);
                                                            summary = jsonStr.substring(0, 200);
                                                        } else {
                                                            summary = String(response).substring(0, 200);
                                                        }
                                                        if (summary.length === 200) summary += "...";
                                                        toolResultSummaries.push(`- ${toolName}: ${summary}`);
                                                    }
                                                }
                                            }
                                        }
                                        // If no function_response parts found after last model, fall back to 0 (shouldn't happen)
                                        const toolResultCount = actualToolResultCount > 0 ? actualToolResultCount : 0;

                                        // Find the LAST user message (which is the current turn's request)
                                        const lastUserContent = [...llmData.contents].reverse().find((c: any) => c.role === "user");
                                        const userPromptFull =
                                            lastUserContent?.parts
                                                ?.map((p: any) => p.text || "")
                                                .join(" ")
                                                .trim() || "";
                                        const userPromptSnippet = userPromptFull.substring(0, 5000);

                                        // Build prompt text with tool result summaries
                                        let toolResultsSection = "";
                                        if (toolResultSummaries.length > 0) {
                                            toolResultsSection = "\n\nTool Results:\n" + toolResultSummaries.join("\n");
                                        }

                                        promptText = `[Following ${toolResultCount} tool result(s)]\nOriginal request: ${userPromptSnippet || "N/A"}${userPromptFull.length > 5000 ? "..." : ""}${toolResultsSection}`;
                                    } else {
                                        // Regular LLM call - find the last user message
                                        const lastUserContent = [...llmData.contents].reverse().find((c: any) => c.role === "user");
                                        if (lastUserContent && lastUserContent.parts) {
                                            promptText = lastUserContent.parts
                                                .map((p: any) => p.text || "") // Handle cases where text might be null/undefined
                                                .join("\n")
                                                .trim();
                                        }
                                    }
                                }
                                const llmCallData: LLMCallData = {
                                    modelName: llmData?.model || "Unknown Model",
                                    promptPreview: promptText || "No text in user prompt.", // Fallback for empty prompt
                                };
                                ensureAgentMetrics(agentInstanceId, statusUpdateAgentName);
                                inProgressLlmCalls.set(agentInstanceId, { timestamp: eventTimestamp, modelName: llmCallData.modelName });
                                visualizerSteps.push({
                                    id: `vstep-llmcall-${visualizerSteps.length}-${eventId}`,
                                    type: "AGENT_LLM_CALL",
                                    timestamp: eventTimestamp,
                                    title: `${statusUpdateAgentName}: LLM Call`,
                                    source: statusUpdateAgentName,
                                    target: "LLM",
                                    data: { llmCall: llmCallData },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "llm_response": {
                                const openCallForPerf = inProgressLlmCalls.get(agentInstanceId);
                                if (openCallForPerf) {
                                    const duration = new Date(eventTimestamp).getTime() - new Date(openCallForPerf.timestamp).getTime();
                                    const agentMetrics = ensureAgentMetrics(agentInstanceId, statusUpdateAgentName);
                                    agentMetrics.llmCalls.push({ modelName: openCallForPerf.modelName, durationMs: duration, timestamp: openCallForPerf.timestamp });
                                    inProgressLlmCalls.delete(agentInstanceId);
                                }

                                const llmResponseData = signalData.data as any;
                                const contentParts = llmResponseData?.content?.parts as any[];
                                const functionCallParts = contentParts?.filter(p => p.function_call);

                                if (functionCallParts && functionCallParts.length > 0) {
                                    flushAggregatedTextStep(currentEventOwningTaskId);
                                    lastFlushedAgentResponseText = null;
                                    activeFunctionCallIdByTask.delete(currentEventOwningTaskId);

                                    const decisions: ToolDecision[] = functionCallParts.map(p => ({
                                        functionCallId: p.function_call.id,
                                        toolName: p.function_call.name,
                                        toolArguments: p.function_call.args || {},
                                        isPeerDelegation: p.function_call.name?.startsWith("peer_") || p.function_call.name?.startsWith("workflow_"),
                                    }));
                                    const toolDecisionData: ToolDecisionData = { decisions, isParallel: decisions.length > 1 };

                                    const delegationInfos: DelegationInfo[] = [];
                                    const claimedSubTaskIds = new Set<string>();
                                    decisions.forEach(decision => {
                                        if (decision.isPeerDelegation) {
                                            let peerAgentActualName = decision.toolName;
                                            if (decision.toolName.startsWith("peer_")) {
                                                peerAgentActualName = decision.toolName.substring(5);
                                            } else if (decision.toolName.startsWith("workflow_")) {
                                                peerAgentActualName = decision.toolName.substring(9);
                                            }

                                            for (const stId in allMonitoredTasks) {
                                                const candSubTask = allMonitoredTasks[stId];
                                                if (claimedSubTaskIds.has(candSubTask.taskId)) continue;

                                                const candSubTaskParentId = getParentTaskIdFromTaskObject(candSubTask);

                                                if (candSubTaskParentId === currentEventOwningTaskId && candSubTask.events && candSubTask.events.length > 0) {
                                                    const subTaskCreationRequest = candSubTask.events.find(e => e.direction === "request" && e.full_payload?.params?.message?.metadata?.function_call_id === decision.functionCallId);
                                                    if (subTaskCreationRequest && new Date(getEventTimestamp(subTaskCreationRequest)).getTime() >= new Date(eventTimestamp).getTime()) {
                                                        const delInfo: DelegationInfo = {
                                                            functionCallId: decision.functionCallId,
                                                            peerAgentName: peerAgentActualName,
                                                            subTaskId: candSubTask.taskId,
                                                        };
                                                        delegationInfos.push(delInfo);
                                                        functionCallIdToDelegationInfoMap.set(decision.functionCallId, delInfo);
                                                        if (candSubTask.taskId) {
                                                            subTaskToFunctionCallIdMap.set(candSubTask.taskId, decision.functionCallId);
                                                            claimedSubTaskIds.add(candSubTask.taskId);
                                                        }
                                                        break;
                                                    }
                                                }
                                            }
                                        }
                                    });

                                    const toolDecisionStep: VisualizerStep = {
                                        id: `vstep-tooldecision-${visualizerSteps.length}-${eventId}`,
                                        type: "AGENT_LLM_RESPONSE_TOOL_DECISION",
                                        timestamp: eventTimestamp,
                                        title: `LLM: Tool Decision${toolDecisionData.isParallel ? " (Parallel)" : ""}`,
                                        source: "LLM",
                                        target: statusUpdateAgentName,
                                        data: { toolDecision: toolDecisionData },
                                        rawEventIds: [eventId],
                                        delegationInfo: delegationInfos.length > 0 ? delegationInfos : undefined,
                                        isSubTaskStep: currentEventNestingLevel > 0,
                                        nestingLevel: currentEventNestingLevel,
                                        owningTaskId: currentEventOwningTaskId,
                                        functionCallId: functionCallIdForStep,
                                    };
                                    visualizerSteps.push(toolDecisionStep);

                                    const parallelBlockId = toolDecisionData.isParallel ? toolDecisionStep.id : undefined;

                                    // --- Performance Data Collection: Start timers for all decided tool calls ---
                                    const invokingAgentInstanceId = agentInstanceId;
                                    ensureAgentMetrics(invokingAgentInstanceId, statusUpdateAgentName);

                                    decisions.forEach(decision => {
                                        const subTaskId = decision.isPeerDelegation ? functionCallIdToDelegationInfoMap.get(decision.functionCallId)?.subTaskId : undefined;

                                        // Don't add if it's already being tracked (should not happen, but safe)
                                        if (!inProgressToolCalls.has(decision.functionCallId)) {
                                            inProgressToolCalls.set(decision.functionCallId, {
                                                timestamp: eventTimestamp, // Start timer at the moment of decision
                                                toolName: decision.toolName,
                                                isPeer: decision.isPeerDelegation,
                                                invokingAgentInstanceId: invokingAgentInstanceId,
                                                subTaskId: subTaskId,
                                                parallelBlockId: parallelBlockId,
                                            });
                                        }
                                    });
                                    // ---
                                } else {
                                    const llmResponseText =
                                        contentParts
                                            ?.filter(p => p.text)
                                            .map(p => p.text)
                                            .join("\n") || "";
                                    const llmResponseToAgentData: LLMResponseToAgentData = {
                                        responsePreview: llmResponseText.substring(0, 200) + (llmResponseText.length > 200 ? "..." : ""),
                                        response: llmResponseText, // Store full response
                                        isFinalResponse: llmResponseData?.partial === false,
                                    };
                                    visualizerSteps.push({
                                        id: `vstep-llmrespagent-${visualizerSteps.length}-${eventId}`,
                                        type: "AGENT_LLM_RESPONSE_TO_AGENT",
                                        timestamp: eventTimestamp,
                                        title: `${statusUpdateAgentName}: LLM Response`,
                                        source: "LLM",
                                        target: statusUpdateAgentName,
                                        data: { llmResponseToAgent: llmResponseToAgentData },
                                        rawEventIds: [eventId],
                                        isSubTaskStep: currentEventNestingLevel > 0,
                                        nestingLevel: currentEventNestingLevel,
                                        owningTaskId: currentEventOwningTaskId,
                                        functionCallId: functionCallIdForStep,
                                    });
                                }
                                break;
                            }
                            case "tool_invocation_start": {
                                const invocationData: ToolInvocationStartData = {
                                    functionCallId: signalData.function_call_id,
                                    toolName: signalData.tool_name,
                                    toolArguments: signalData.tool_args,
                                    isPeerInvocation: signalData.tool_name?.startsWith("peer_") || signalData.tool_name?.startsWith("workflow_"),
                                    parallelGroupId: signalData.parallel_group_id,
                                };

                                const delegationInfo = functionCallIdToDelegationInfoMap.get(signalData.function_call_id);

                                visualizerSteps.push({
                                    id: `vstep-toolinvokestart-${visualizerSteps.length}-${eventId}`,
                                    type: "AGENT_TOOL_INVOCATION_START",
                                    timestamp: eventTimestamp,
                                    title: `${statusUpdateAgentName}: Executing tool ${invocationData.toolName}`,
                                    source: statusUpdateAgentName,
                                    target: invocationData.toolName,
                                    data: { toolInvocationStart: invocationData },
                                    rawEventIds: [eventId],
                                    delegationInfo: delegationInfo ? [delegationInfo] : undefined,
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });
                                break;
                            }
                            case "tool_result": {
                                const functionCallId = signalData.function_call_id;
                                // --- Performance Data Collection ---
                                const openToolCallForPerf = inProgressToolCalls.get(functionCallId);
                                if (openToolCallForPerf) {
                                    const duration = new Date(eventTimestamp).getTime() - new Date(openToolCallForPerf.timestamp).getTime();
                                    const invokingAgentMetrics = report.agents[openToolCallForPerf.invokingAgentInstanceId];
                                    if (invokingAgentMetrics) {
                                        let peerAgentName: string | undefined;
                                        if (openToolCallForPerf.isPeer) {
                                            if (openToolCallForPerf.toolName.startsWith("peer_")) {
                                                peerAgentName = openToolCallForPerf.toolName.substring(5);
                                            } else if (openToolCallForPerf.toolName.startsWith("workflow_")) {
                                                peerAgentName = openToolCallForPerf.toolName.substring(9);
                                            }
                                        }

                                        const toolCallPerf: ToolCallPerformance = {
                                            toolName: openToolCallForPerf.toolName,
                                            durationMs: duration,
                                            isPeer: openToolCallForPerf.isPeer,
                                            timestamp: openToolCallForPerf.timestamp,
                                            peerAgentName: peerAgentName,
                                            subTaskId: openToolCallForPerf.subTaskId,
                                            parallelBlockId: openToolCallForPerf.parallelBlockId,
                                        };
                                        invokingAgentMetrics.toolCalls.push(toolCallPerf);
                                    }
                                    inProgressToolCalls.delete(functionCallId);
                                }
                                // ---

                                const toolResultData: ToolResultData = {
                                    toolName: signalData.tool_name,
                                    functionCallId: functionCallId,
                                    resultData: signalData.result_data,
                                    isPeerResponse: signalData.tool_name?.startsWith("peer_") || signalData.tool_name?.startsWith("workflow_"),
                                };
                                visualizerSteps.push({
                                    id: `vstep-toolresult-${visualizerSteps.length}-${eventId}`,
                                    type: "AGENT_TOOL_EXECUTION_RESULT",
                                    timestamp: eventTimestamp,
                                    title: `${statusUpdateAgentName}: Tool Result - ${toolResultData.toolName}`,
                                    source: toolResultData.toolName,
                                    target: statusUpdateAgentName,
                                    data: { toolResult: toolResultData },
                                    rawEventIds: [eventId],
                                    isSubTaskStep: currentEventNestingLevel > 0,
                                    nestingLevel: currentEventNestingLevel,
                                    owningTaskId: currentEventOwningTaskId,
                                    functionCallId: functionCallIdForStep,
                                });

                                // Check if this is _notify_artifact_save and we have a pending artifact
                                if (signalData.tool_name === "_notify_artifact_save" && functionCallId) {
                                    const pendingArtifact = pendingArtifacts.get(functionCallId);
                                    // Skip intermediate web content artifacts from deep research
                                    if (pendingArtifact && !isIntermediateWebContentArtifact(pendingArtifact.filename)) {
                                        const artifactNotification: ArtifactNotificationData = {
                                            artifactName: pendingArtifact.filename,
                                            version: pendingArtifact.version,
                                            description: pendingArtifact.description,
                                            mimeType: pendingArtifact.mimeType,
                                        };
                                        visualizerSteps.push({
                                            id: `vstep-artifactcreated-${visualizerSteps.length}-${pendingArtifact.eventId}`,
                                            type: "AGENT_ARTIFACT_NOTIFICATION",
                                            timestamp: pendingArtifact.timestamp,
                                            title: `${pendingArtifact.agentName}: Created Artifact - ${artifactNotification.artifactName}`,
                                            source: pendingArtifact.agentName,
                                            target: "User/System",
                                            data: { artifactNotification },
                                            rawEventIds: [pendingArtifact.eventId],
                                            isSubTaskStep: pendingArtifact.nestingLevel > 0,
                                            nestingLevel: pendingArtifact.nestingLevel,
                                            owningTaskId: pendingArtifact.taskId,
                                            functionCallId: functionCallId,
                                        });
                                    }
                                    pendingArtifacts.delete(functionCallId);
                                }
                                break;
                            }
                            case "artifact_creation_progress": {
                                break;
                            }
                            case "artifact_saved": {
                                // Handle new artifact_saved event type
                                flushAggregatedTextStep(currentEventOwningTaskId);

                                const artifactFilename = signalData.filename || "Unnamed Artifact";

                                // Skip intermediate web content artifacts from deep research
                                if (isIntermediateWebContentArtifact(artifactFilename)) {
                                    break;
                                }

                                // Check if this has a function_call_id (from fenced blocks with _notify_artifact_save)
                                const isSyntheticToolCall = signalData.function_call_id && signalData.function_call_id.startsWith("host-notify-");

                                if (isSyntheticToolCall) {
                                    // Queue this artifact - will be created when we see the _notify_artifact_save tool result
                                    pendingArtifacts.set(signalData.function_call_id, {
                                        filename: artifactFilename,
                                        version: signalData.version,
                                        description: signalData.description,
                                        mimeType: signalData.mime_type,
                                        timestamp: eventTimestamp,
                                        agentName: statusUpdateAgentName,
                                        taskId: currentEventOwningTaskId,
                                        nestingLevel: currentEventNestingLevel,
                                        eventId: eventId,
                                    });
                                } else {
                                    // Regular tool call - create node immediately
                                    const artifactNotification: ArtifactNotificationData = {
                                        artifactName: artifactFilename,
                                        version: signalData.version,
                                        description: signalData.description,
                                        mimeType: signalData.mime_type,
                                    };
                                    visualizerSteps.push({
                                        id: `vstep-artifactsaved-${visualizerSteps.length}-${eventId}`,
                                        type: "AGENT_ARTIFACT_NOTIFICATION",
                                        timestamp: eventTimestamp,
                                        title: `${statusUpdateAgentName}: Created Artifact - ${artifactNotification.artifactName}`,
                                        source: statusUpdateAgentName,
                                        target: "User/System",
                                        data: { artifactNotification },
                                        rawEventIds: [eventId],
                                        isSubTaskStep: currentEventNestingLevel > 0,
                                        nestingLevel: currentEventNestingLevel,
                                        owningTaskId: currentEventOwningTaskId,
                                        functionCallId: signalData.function_call_id || functionCallIdForStep,
                                    });
                                }
                                break;
                            }
                            default:
                                console.log(`Received unknown data part type: ${signalType}`, signalData);
                                break;
                        }
                    } else if (part.kind === "text" && part.text) {
                        if (aggregatedTextSourceAgent && aggregatedTextSourceAgent !== statusUpdateAgentName) {
                            flushAggregatedTextStep(currentEventOwningTaskId);
                            lastFlushedAgentResponseText = null;
                        }
                        if (!aggregatedTextSourceAgent) {
                            aggregatedTextSourceAgent = statusUpdateAgentName;
                            aggregatedTextTimestamp = eventTimestamp;
                            aggregatedTextIsForwardedContext = isForwardedMessage;
                        }
                        currentAggregatedText += part.text;
                        aggregatedRawEventIds.push(eventId);
                    }
                }
            }
            return;
        }

        // ARTIFACT UPDATE
        if (event.direction === "artifact_update" && payload?.result?.artifact) {
            flushAggregatedTextStep(currentEventOwningTaskId);
            const artifactData = payload.result.artifact as Artifact;
            const artifactName = artifactData.name || "Unnamed Artifact";

            // Skip intermediate web content artifacts from deep research
            if (isIntermediateWebContentArtifact(artifactName)) {
                return;
            }

            const artifactAgentName = (artifactData.metadata?.agent_name as string) || event.source_entity || "Agent";
            let mimeType: string | undefined = undefined;
            if (artifactData.parts && artifactData.parts.length > 0) {
                const firstPart = artifactData.parts[0];
                if (firstPart.kind === "file") {
                    mimeType = (firstPart as FilePart).file.mimeType || undefined;
                } else if (firstPart.metadata?.mime_type) {
                    mimeType = firstPart.metadata.mime_type as string;
                }
            }
            const artifactNotification: ArtifactNotificationData = {
                artifactName: artifactName,
                version: typeof artifactData.metadata?.version === "number" ? artifactData.metadata.version : undefined,
                description: artifactData.description || undefined,
                mimeType,
            };
            visualizerSteps.push({
                id: `vstep-artifactnotify-${visualizerSteps.length}-${eventId}`,
                type: "AGENT_ARTIFACT_NOTIFICATION",
                timestamp: eventTimestamp,
                title: `${artifactAgentName}: Artifact Update - ${artifactNotification.artifactName}`,
                source: artifactAgentName,
                target: "User/System",
                data: { artifactNotification },
                rawEventIds: [eventId],
                isSubTaskStep: currentEventNestingLevel > 0,
                nestingLevel: currentEventNestingLevel,
                owningTaskId: currentEventOwningTaskId,
                functionCallId: functionCallIdForStep,
            });
            return;
        }

        // FINAL RESPONSE / TASK COMPLETION
        if (["response", "task"].includes(event.direction) && payload?.result?.status?.state) {
            if (currentAggregatedText.trim()) {
                flushAggregatedTextStep(currentEventOwningTaskId);
            }

            const result = payload.result as any;
            const finalState = result.status.state as string;
            const responseAgentName = result.metadata?.agent_name || result.status?.message?.metadata?.agent_name || event.source_entity || "Agent";

            if (["completed", "failed", "canceled"].includes(finalState)) {
                const stepType: VisualizerStepType = finalState === "completed" ? "TASK_COMPLETED" : "TASK_FAILED";
                const title = `${responseAgentName}: Task ${finalState.charAt(0).toUpperCase() + finalState.slice(1)}`;
                let dataPayload: any = {};
                let finalMessageTextFromEvent = "";
                if (result.status.message?.parts) {
                    const textPart = result.status.message.parts.find((p: any) => p.kind === "text") as TextPart | undefined;
                    if (textPart?.text) finalMessageTextFromEvent = textPart.text.trim();
                }

                const isRootTaskFinalEvent = currentEventOwningTaskId === parentTaskObject.taskId;
                const includeFinalMessage = finalMessageTextFromEvent && (!isRootTaskFinalEvent || finalMessageTextFromEvent !== lastFlushedAgentResponseText);

                if (stepType === "TASK_COMPLETED") {
                    dataPayload = { finalMessage: includeFinalMessage ? finalMessageTextFromEvent : undefined };
                } else {
                    const errorMessage = includeFinalMessage ? finalMessageTextFromEvent : `Task ${finalState}.`;
                    const errorDetails: { message: string; code?: number | string; details?: any } = { message: errorMessage };
                    const rpcError = payload.error as JSONRPCError | undefined;
                    if (rpcError) {
                        errorDetails.message = rpcError.message || errorDetails.message;
                        errorDetails.code = rpcError.code;
                        if (rpcError.data) errorDetails.details = rpcError.data;
                    }
                    if (result.error) {
                        errorDetails.message = result.error.message || errorDetails.message;
                        errorDetails.code = result.error.code || errorDetails.code;
                        errorDetails.details = result.error.data || errorDetails.details;
                    }
                    dataPayload = { errorDetails };
                }
                visualizerSteps.push({
                    id: `vstep-${finalState}-${visualizerSteps.length}-${eventId}`,
                    type: stepType,
                    timestamp: eventTimestamp,
                    title,
                    source: responseAgentName,
                    target: "User",
                    data: dataPayload,
                    rawEventIds: [eventId],
                    isSubTaskStep: currentEventNestingLevel > 0,
                    nestingLevel: currentEventNestingLevel,
                    owningTaskId: currentEventOwningTaskId,
                    functionCallId: functionCallIdForStep,
                });
                if (isRootTaskFinalEvent) lastFlushedAgentResponseText = null;
                return;
            }
        }

        // Fallback for flushing text if no other condition matched for the current event
        const isStreamingTextEvent = event.direction === "status-update" && payload?.result?.status?.message?.parts?.some((p: any) => p.kind === "text");
        let currentEventSourceAgentName = event.source_entity;
        if (payload?.result?.status?.message?.metadata?.forwarded_from_peer) {
            currentEventSourceAgentName = payload.result.status.message.metadata.forwarded_from_peer;
        } else if (payload?.result?.metadata?.agent_name) {
            currentEventSourceAgentName = payload.result.metadata.agent_name;
        } else if (payload?.result?.status?.message?.metadata?.agent_name) {
            currentEventSourceAgentName = payload.result.status.message.metadata.agent_name;
        }

        if (currentAggregatedText.trim() && aggregatedTextSourceAgent) {
            if (!isStreamingTextEvent || (isStreamingTextEvent && currentEventSourceAgentName !== aggregatedTextSourceAgent)) {
                flushAggregatedTextStep(currentEventOwningTaskId);
                if (taskNestingLevels.get(aggregatedRawEventIds[0]?.split("-")[1] || parentTaskObject.taskId) === 0 && !aggregatedTextIsForwardedContext) {
                    lastFlushedAgentResponseText = null;
                }
            }
        }
    });

    // Final flush for any remaining aggregated text
    const lastEventTaskId = sortedEvents.length > 0 ? sortedEvents[sortedEvents.length - 1].task_id || parentTaskObject.taskId : parentTaskObject.taskId;
    flushAggregatedTextStep(lastEventTaskId);

    const startTime = sortedEvents[0] ? getEventTimestamp(sortedEvents[0]) : parentTaskObject.firstSeen.toISOString();
    let endTime: string | undefined = undefined;
    let taskStatus: TaskState = "working";

    const rootTaskSteps = visualizerSteps.filter(step => step.owningTaskId === parentTaskObject.taskId);
    const lastRootTaskStep = rootTaskSteps.length > 0 ? rootTaskSteps[rootTaskSteps.length - 1] : null;

    if (lastRootTaskStep) {
        if (lastRootTaskStep.type === "TASK_COMPLETED") {
            taskStatus = "completed";
            endTime = lastRootTaskStep.timestamp;
        } else if (lastRootTaskStep.type === "TASK_FAILED") {
            taskStatus = "failed";
            endTime = lastRootTaskStep.timestamp;
        }
    }
    if (taskStatus === "working" && sortedEvents.length > 0) {
        const lastOverallEvent = sortedEvents[sortedEvents.length - 1];
        const lastEventTask = allMonitoredTasks[lastOverallEvent.task_id || parentTaskObject.taskId];
        if (lastEventTask) {
            // Future enhancement: check TaskFE status directly
        }
    }

    let totalDurationMs: number | undefined = undefined;
    if (startTime && endTime) {
        totalDurationMs = new Date(endTime).getTime() - new Date(startTime).getTime();
    }

    // If the task has reached a terminal state, we should not show a "current" status text.
    if (["completed", "failed", "canceled", "rejected"].includes(taskStatus)) {
        lastStatusText = undefined;
    }

    const visualizedTask: VisualizedTask = {
        taskId: parentTaskObject.taskId,
        initialRequestText: parentTaskObject.initialRequestText,
        status: taskStatus,
        currentStatusText: lastStatusText,
        startTime: startTime,
        endTime: endTime,
        durationMs: totalDurationMs,
        steps: visualizerSteps,
    };

    // Post-process to aggregate final text for completed tasks
    visualizedTask.steps.forEach((step, index) => {
        if (step.type === "TASK_COMPLETED") {
            let finalTurnText = "";
            // Walk backwards from the completed step
            for (let i = index - 1; i >= 0; i--) {
                const prevStep = visualizedTask.steps[i];
                // Stop if we hit a step that isn't a simple text response from the same agent
                if (prevStep.type !== "AGENT_RESPONSE_TEXT" || prevStep.source !== step.source) {
                    break;
                }
                // Prepend the text
                finalTurnText = prevStep.data.text + finalTurnText;
            }
            // Also include the text from the final event itself, if any
            if (step.data.finalMessage) {
                finalTurnText += step.data.finalMessage;
            }
            step.data.finalMessage = finalTurnText.trim() || undefined;
        }
    });

    // --- Phase 2: Post-Processing and Final Aggregation ---

    // 1. Calculate aggregated timings for each agent
    Object.values(report.agents).forEach(agentMetrics => {
        // 1a. Calculate total LLM time
        agentMetrics.totalLlmTimeMs = agentMetrics.llmCalls.reduce((sum, call) => sum + call.durationMs, 0);

        // 1b. Calculate total Tool time, handling parallelism
        const sequentialCalls = agentMetrics.toolCalls.filter(call => !call.parallelBlockId);
        const parallelBlocks = new Map<string, ToolCallPerformance[]>();

        agentMetrics.toolCalls.forEach(call => {
            if (call.parallelBlockId) {
                if (!parallelBlocks.has(call.parallelBlockId)) {
                    parallelBlocks.set(call.parallelBlockId, []);
                }
                parallelBlocks.get(call.parallelBlockId)!.push(call);
            }
        });

        const sequentialTime = sequentialCalls.reduce((sum, call) => sum + call.durationMs, 0);

        let parallelTime = 0;
        parallelBlocks.forEach(blockCalls => {
            if (blockCalls.length > 0) {
                const startTime = Math.min(...blockCalls.map(call => new Date(call.timestamp).getTime()));
                const endTime = Math.max(...blockCalls.map(call => new Date(call.timestamp).getTime() + call.durationMs));
                parallelTime += endTime - startTime;
            }
        });

        agentMetrics.totalToolTimeMs = sequentialTime + parallelTime;
    });

    // 2. Assign unique display names for parallel instances
    const agentInstancesByName = new Map<string, AgentPerformanceMetrics[]>();
    Object.values(report.agents).forEach(agentMetrics => {
        if (!agentInstancesByName.has(agentMetrics.agentName)) {
            agentInstancesByName.set(agentMetrics.agentName, []);
        }
        agentInstancesByName.get(agentMetrics.agentName)!.push(agentMetrics);
    });

    agentInstancesByName.forEach(instances => {
        if (instances.length > 1) {
            // Sort instances by their first activity time to ensure consistent naming
            instances.sort((a, b) => {
                const getFirstTimestamp = (metrics: AgentPerformanceMetrics): number => {
                    const allTimestamps = [...metrics.llmCalls.map(c => new Date(c.timestamp).getTime()), ...metrics.toolCalls.map(c => new Date(c.timestamp).getTime())];
                    return allTimestamps.length > 0 ? Math.min(...allTimestamps) : Infinity;
                };
                return getFirstTimestamp(a) - getFirstTimestamp(b);
            });

            // Assign numbered display names
            instances.forEach((instance, index) => {
                instance.displayName = `${instance.agentName} (${index + 1})`;
            });
        }
    });

    // 3. Link peer delegations to unique display names
    const subTaskToDisplayNameMap = new Map<string, string>();
    Object.values(report.agents).forEach(agentMetrics => {
        // The instanceId is "AgentName:owningTaskId"
        const owningTaskId = agentMetrics.instanceId.split(":").slice(1).join(":");
        if (owningTaskId) {
            subTaskToDisplayNameMap.set(owningTaskId, agentMetrics.displayName);
        }
    });

    Object.values(report.agents).forEach(agentMetrics => {
        agentMetrics.toolCalls.forEach(call => {
            if (call.isPeer && call.subTaskId) {
                const peerDisplayName = subTaskToDisplayNameMap.get(call.subTaskId);
                if (peerDisplayName) {
                    call.peerAgentName = peerDisplayName;
                }
            }
        });
    });

    // 4. Calculate overall task duration for the report
    if (totalDurationMs !== undefined) {
        report.overall.totalTaskDurationMs = totalDurationMs;
    }

    // --- End of Phase 2 ---

    visualizedTask.performanceReport = report;

    return visualizedTask;
};
