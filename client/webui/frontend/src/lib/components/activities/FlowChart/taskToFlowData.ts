import type { Node, Edge } from "@xyflow/react";

import type { VisualizerStep } from "@/lib/types";

import {
    addNode,
    type TimelineLayoutManager,
    type NodeInstance,
    LANE_X_POSITIONS,
    Y_START,
    NODE_HEIGHT,
    NODE_WIDTH,
    VERTICAL_SPACING,
    GROUP_PADDING_Y,
    GROUP_PADDING_X,
    USER_NODE_Y_OFFSET,
    generateNodeId,
    getCurrentPhase,
    getCurrentSubflow,
    findSubflowBySubTaskId,
    resolveSubflowContext,
    isParallelFlow,
    findToolInstanceByNameEnhanced,
    createNewMainPhase,
    startNewSubflow,
    startNewWorkflowContext,
    createWorkflowNodeInContext,
    createNewToolNodeInContext,
    createTimelineEdge,
    createNewUserNodeAtBottom,
    createAgentRegistry,
    getAgentHandle,
    isOrchestratorAgent,
} from "./taskToFlowData.helpers";
import { EdgeAnimationService } from "./edgeAnimationService";

// Relevant step types that should be processed in the flow chart
const RELEVANT_STEP_TYPES = ["USER_REQUEST", "AGENT_LLM_CALL", "AGENT_LLM_RESPONSE_TO_AGENT", "AGENT_LLM_RESPONSE_TOOL_DECISION", "AGENT_TOOL_INVOCATION_START", "AGENT_TOOL_EXECUTION_RESULT", "AGENT_RESPONSE_TEXT", "TASK_COMPLETED", "TASK_FAILED", "WORKFLOW_EXECUTION_START", "WORKFLOW_NODE_EXECUTION_START", "WORKFLOW_NODE_EXECUTION_RESULT", "WORKFLOW_EXECUTION_RESULT"];

interface FlowData {
    nodes: Node[];
    edges: Edge[];
}

export interface AnimatedEdgeData {
    visualizerStepId: string;
    isAnimated?: boolean;
    animationType?: "request" | "response" | "static";
}

function handleUserRequest(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const targetAgentName = step.target as string;
    const sanitizedTargetAgentName = targetAgentName.replace(/[^a-zA-Z0-9_]/g, "_");

    const currentPhase = getCurrentPhase(manager);
    const currentSubflow = getCurrentSubflow(manager);

    let lastAgentNode: NodeInstance | undefined;
    let connectToLastAgent = false;

    if (currentSubflow) {
        lastAgentNode = currentSubflow.peerAgent;
        if (lastAgentNode.id.startsWith(sanitizedTargetAgentName + "_")) {
            connectToLastAgent = true;
        }
    } else if (currentPhase) {
        lastAgentNode = currentPhase.orchestratorAgent;
        if (lastAgentNode.id.startsWith(sanitizedTargetAgentName + "_")) {
            connectToLastAgent = true;
        }
    }

    if (connectToLastAgent && lastAgentNode && currentPhase) {
        // Continued conversation: Create a "middle" user node and connect it to the last agent.
        manager.userNodeCounter++;
        const userNodeId = generateNodeId(manager, `User_continue_${manager.userNodeCounter}`);

        // Position the new user node at the current bottom of the flow.
        const userNodeY = manager.nextAvailableGlobalY;

        const userNode: Node = {
            id: userNodeId,
            type: "userNode",
            position: { x: LANE_X_POSITIONS.USER, y: userNodeY },
            // No isTopNode or isBottomNode, so it will be a "middle" node with a right handle.
            data: { label: "User", visualizerStepId: step.id },
        };

        addNode(nodes, manager.allCreatedNodeIds, userNode);
        manager.nodePositions.set(userNodeId, userNode.position);

        const userNodeInstance: NodeInstance = {
            id: userNodeId,
            yPosition: userNodeY,
            height: NODE_HEIGHT,
            width: NODE_WIDTH,
        };

        // Add to tracking
        currentPhase.userNodes.push(userNodeInstance);
        manager.allUserNodes.push(userNodeInstance);

        // Update layout tracking to position subsequent nodes correctly.
        const newMaxY = userNodeY + NODE_HEIGHT;
        // An agent will be created at the same Y level, so we take the max.
        lastAgentNode.yPosition = Math.max(lastAgentNode.yPosition, userNodeY);
        currentPhase.maxY = Math.max(currentPhase.maxY, newMaxY, lastAgentNode.yPosition + NODE_HEIGHT);
        manager.nextAvailableGlobalY = currentPhase.maxY + VERTICAL_SPACING;

        // The agent receiving the request is the target.
        const targetAgentHandle = isOrchestratorAgent(targetAgentName) ? "orch-left-input" : "peer-left-input";

        createTimelineEdge(
            userNodeInstance.id,
            lastAgentNode.id,
            step,
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            "user-right-output", // Source from the new right handle
            targetAgentHandle // Target the top of the agent
        );
    } else {
        // Original behavior: create a new phase for the user request.
        const phase = createNewMainPhase(manager, targetAgentName, step, nodes);

        const userNodeId = generateNodeId(manager, `User_${phase.id}`);
        const userNode: Node = {
            id: userNodeId,
            type: "userNode",
            position: { x: LANE_X_POSITIONS.USER, y: phase.orchestratorAgent.yPosition - USER_NODE_Y_OFFSET },
            data: { label: "User", visualizerStepId: step.id, isTopNode: true },
        };
        addNode(nodes, manager.allCreatedNodeIds, userNode);
        manager.nodePositions.set(userNodeId, userNode.position);

        const userNodeInstance = { id: userNodeId, yPosition: userNode.position.y, height: NODE_HEIGHT, width: NODE_WIDTH };
        phase.userNodes.push(userNodeInstance); // Add to userNodes array
        manager.allUserNodes.push(userNodeInstance); // Add to global tracking
        manager.userNodeCounter++;

        phase.maxY = Math.max(phase.maxY, userNode.position.y + NODE_HEIGHT);
        manager.nextAvailableGlobalY = phase.maxY + VERTICAL_SPACING;

        createTimelineEdge(
            userNodeId,
            phase.orchestratorAgent.id,
            step,
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            "user-bottom-output", // UserNode output
            "orch-top-input" // OrchestratorAgent input from user
        );
    }
}

function handleLLMCall(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    // Use enhanced context resolution
    const subflow = resolveSubflowContext(manager, step);

    const sourceAgentNodeId = subflow ? subflow.peerAgent.id : currentPhase.orchestratorAgent.id;
    const llmToolInstance = createNewToolNodeInContext(manager, "LLM", "llmNode", step, nodes, subflow, true);

    if (llmToolInstance) {
        createTimelineEdge(
            sourceAgentNodeId,
            llmToolInstance.id,
            step,
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            subflow ? "peer-right-output-tools" : "orch-right-output-tools", // Agent output to LLM
            "llm-left-input" // LLM input
        );
    }
}

function handleLLMResponseToAgent(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    // If this is a parallel tool decision with multiple peer agents delegation, set up the parallel flow context
    if (step.type === "AGENT_LLM_RESPONSE_TOOL_DECISION" && step.data.toolDecision?.isParallel) {
        const parallelFlowId = `parallel-${step.id}`;
        if (step.data.toolDecision.decisions.filter(d => d.isPeerDelegation).length > 1) {
            manager.parallelFlows.set(parallelFlowId, {
                subflowFunctionCallIds: step.data.toolDecision.decisions.filter(d => d.isPeerDelegation).map(d => d.functionCallId),
                completedSubflows: new Set(),
                startX: LANE_X_POSITIONS.MAIN_FLOW - 50,
                startY: manager.nextAvailableGlobalY,
                currentXOffset: 0,
                maxHeight: 0,
            });
        }
    }

    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    // Use enhanced context resolution
    const subflow = resolveSubflowContext(manager, step);

    let llmNodeId: string | undefined;
    // LLM node should exist from a previous AGENT_LLM_CALL
    // Find the most recent LLM instance within the correct context
    const context = subflow || currentPhase;

    const llmInstance = findToolInstanceByNameEnhanced(context.toolInstances, "LLM", nodes, step.functionCallId);

    if (llmInstance) {
        llmNodeId = llmInstance.id;
    } else {
        console.error(`[Timeline] LLM node not found for step type ${step.type}: ${step.id}. Cannot create edge.`);
        return;
    }

    // Target is the agent that received the response
    const targetAgentName = step.target || "UnknownAgent";
    let targetAgentNodeId: string | undefined;
    let targetAgentHandleId: string | undefined;

    if (subflow) {
        targetAgentNodeId = subflow.peerAgent.id;
        targetAgentHandleId = "peer-right-input-tools";
    } else if (currentPhase.orchestratorAgent.id.startsWith(targetAgentName.replace(/[^a-zA-Z0-9_]/g, "_") + "_")) {
        targetAgentNodeId = currentPhase.orchestratorAgent.id;
        targetAgentHandleId = "orch-right-input-tools";
    }

    if (llmNodeId && targetAgentNodeId && targetAgentHandleId) {
        createTimelineEdge(
            llmNodeId,
            targetAgentNodeId,
            step,
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            "llm-bottom-output", // LLM's bottom output handle
            targetAgentHandleId // Agent's right input handle
        );
    } else {
        console.error(`[Timeline] Could not determine target agent node ID or handle for step type ${step.type}: ${step.id}. Target agent name: ${targetAgentName}. Edge will be missing.`);
    }
}

function handleToolInvocationStart(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    const sourceName = step.source || "UnknownSource";
    const targetToolName = step.target || "UnknownTool";

    // Skip workflow tool invocations as they are handled by WORKFLOW_EXECUTION_START
    if (targetToolName.startsWith("workflow_")) {
        return;
    }

    const isPeerDelegation = step.data.toolInvocationStart?.isPeerInvocation || targetToolName.startsWith("peer_");

    if (isPeerDelegation) {
        const peerAgentName = targetToolName.startsWith("peer_") ? targetToolName.substring(5) : targetToolName;

        // Instead of relying on the current subflow context, which can be polluted by the
        // first parallel node, we find the source agent directly from the registry.
        const sourceAgentInfo = manager.agentRegistry.findAgentByName(sourceName);
        if (!sourceAgentInfo) {
            console.error(`[Timeline] Could not find source agent in registry: ${sourceName} for step ${step.id}`);
            return;
        }

        const sourceAgent = sourceAgentInfo.nodeInstance;
        // All agent-to-agent delegations use the bottom-to-top handles.
        const sourceHandle = getAgentHandle(sourceAgentInfo.type, "output", "bottom");

        const isParallel = isParallelFlow(step, manager);

        const subflowContext = startNewSubflow(manager, peerAgentName, step, nodes, isParallel);
        if (subflowContext) {
            createTimelineEdge(sourceAgent.id, subflowContext.peerAgent.id, step, edges, manager, edgeAnimationService, processedSteps, sourceHandle, "peer-top-input");
        }
    } else {
        // Regular tool call
        const subflow = resolveSubflowContext(manager, step);
        let sourceNodeId: string;
        let sourceHandle: string;

        if (subflow) {
            sourceNodeId = subflow.peerAgent.id;
            sourceHandle = "peer-right-output-tools";
        } else {
            const sourceAgent = manager.agentRegistry.findAgentByName(sourceName);
            if (sourceAgent) {
                sourceNodeId = sourceAgent.id;
                sourceHandle = getAgentHandle(sourceAgent.type, "output", "right");
            } else {
                sourceNodeId = currentPhase.orchestratorAgent.id;
                sourceHandle = "orch-right-output-tools";
            }
        }

        const toolInstance = createNewToolNodeInContext(manager, targetToolName, "genericToolNode", step, nodes, subflow);
        if (toolInstance) {
            createTimelineEdge(sourceNodeId, toolInstance.id, step, edges, manager, edgeAnimationService, processedSteps, sourceHandle, `${toolInstance.id}-tool-left-input`);
        }
    }
}

function handleToolExecutionResult(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    const stepSource = step.source || "UnknownSource";
    const toolName = step.data.toolResult?.toolName || stepSource;
    const targetAgentName = step.target || "OrchestratorAgent";
    const isWorkflowReturn = toolName.startsWith("workflow_");

    if (step.data.toolResult?.isPeerResponse || isWorkflowReturn) {
        const returningFunctionCallId = step.data.toolResult?.functionCallId;

        // 1. FIRST, check if this return belongs to any active parallel flow.
        const parallelFlowEntry = Array.from(manager.parallelFlows.entries()).find(
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            ([_id, pf]) => pf.subflowFunctionCallIds.includes(returningFunctionCallId || "")
        );

        if (parallelFlowEntry) {
            // It's a parallel return. Handle the special join logic.
            const [parallelFlowId, parallelFlow] = parallelFlowEntry;

            parallelFlow.completedSubflows.add(returningFunctionCallId || "");

            if (parallelFlow.completedSubflows.size < parallelFlow.subflowFunctionCallIds.length) {
                // Not all parallel tasks are done yet. Just record completion and wait.
                return;
            }

            // 2. ALL parallel tasks are done. Create a SINGLE "join" node.
            const sourceSubflows = currentPhase.subflows.filter(sf => parallelFlow.subflowFunctionCallIds.includes(sf.functionCallId));

            const joinTargetAgentName = step.target || "OrchestratorAgent";
            let joinNode: NodeInstance;
            let joinNodeHandle: string;

            if (isOrchestratorAgent(joinTargetAgentName)) {
                // The parallel tasks are returning to the main orchestrator.
                manager.indentationLevel = 0;
                const newOrchestratorPhase = createNewMainPhase(manager, joinTargetAgentName, step, nodes);
                joinNode = newOrchestratorPhase.orchestratorAgent;
                joinNodeHandle = "orch-top-input";
                manager.currentSubflowIndex = -1; // Return to main flow context
            } else {
                // The parallel tasks are returning to a PEER agent (nested parallel).
                // Create ONE new instance of that peer agent for them to join to.
                manager.indentationLevel = Math.max(0, manager.indentationLevel - 1);
                const newSubflowForJoin = startNewSubflow(manager, joinTargetAgentName, step, nodes, false);
                if (!newSubflowForJoin) return;
                joinNode = newSubflowForJoin.peerAgent;
                joinNodeHandle = "peer-top-input";
            }

            // 3. Connect ALL completed parallel agents to this single join node.
            sourceSubflows.forEach(subflow => {
                // Determine source node ID
                let sourceNodeId = subflow.lastSubflow?.peerAgent.id ?? subflow.peerAgent.id;
                // If it's a workflow subflow, prefer finishNodeId
                if (subflow.finishNodeId) {
                    sourceNodeId = subflow.finishNodeId;
                }

                createTimelineEdge(
                    sourceNodeId,
                    joinNode.id,
                    step, // Use the final step as the representative event for the join
                    edges,
                    manager,
                    edgeAnimationService,
                    processedSteps,
                    "peer-bottom-output",
                    joinNodeHandle
                );
            });

            // 4. Clean up the completed parallel flow to prevent reuse.
            manager.parallelFlows.delete(parallelFlowId);

            return; // Exit after handling the parallel join.
        }

        // If we reach here, it's a NON-PARALLEL (sequential) peer/workflow return.

        // Determine Source Node ID
        let sourceNodeId: string | undefined;

        if (isWorkflowReturn) {
            const lookupId = returningFunctionCallId || step.functionCallId;
            const workflowSubflow = manager.phases
                .flatMap(p => p.subflows)
                .find(sf => sf.functionCallId === lookupId);
            if (workflowSubflow) {
                sourceNodeId = workflowSubflow.finishNodeId || workflowSubflow.peerAgent.id;
            } else {
                // Fallback: try to find the workflow agent by name if subflow lookup fails
                const workflowName = toolName.replace("workflow_", "");
                const agentInfo = manager.agentRegistry.findAgentByName(workflowName);
                if (agentInfo) sourceNodeId = agentInfo.id;
            }
        } else {
            const sourceAgent = manager.agentRegistry.findAgentByName(stepSource.startsWith("peer_") ? stepSource.substring(5) : stepSource);
            if (sourceAgent) sourceNodeId = sourceAgent.id;
        }

        if (!sourceNodeId) {
            console.error(`[Timeline] Source node not found for response: ${stepSource}.`);
            return;
        }

        if (isOrchestratorAgent(targetAgentName)) {
            manager.indentationLevel = 0;
            const newOrchestratorPhase = createNewMainPhase(manager, targetAgentName, step, nodes);
            createTimelineEdge(sourceNodeId, newOrchestratorPhase.orchestratorAgent.id, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", "orch-top-input");
            manager.currentSubflowIndex = -1;
        } else {
            // Peer-to-peer sequential return.
            manager.indentationLevel = Math.max(0, manager.indentationLevel - 1);

            // Check if we need to consider parallel flow context for this return
            const isWithinParallelContext = isParallelFlow(step, manager) || Array.from(manager.parallelFlows.values()).some(pf => pf.subflowFunctionCallIds.some(id => currentPhase.subflows.some(sf => sf.functionCallId === id)));

            const newSubflow = startNewSubflow(manager, targetAgentName, step, nodes, isWithinParallelContext);
            if (newSubflow) {
                createTimelineEdge(sourceNodeId, newSubflow.peerAgent.id, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", "peer-top-input");
            }
        }
    } else {
        // Regular tool (non-peer, non-workflow) returning result
        let toolNodeId: string | undefined;
        const subflow = resolveSubflowContext(manager, step);
        const context = subflow || currentPhase;

        const toolInstance = findToolInstanceByNameEnhanced(context.toolInstances, stepSource, nodes, step.functionCallId);
        if (toolInstance) {
            toolNodeId = toolInstance.id;
        }

        if (toolNodeId) {
            let receivingAgentNodeId: string;
            let targetHandle: string;

            if (subflow) {
                receivingAgentNodeId = subflow.peerAgent.id;
                targetHandle = "peer-right-input-tools";
            } else {
                const targetAgent = manager.agentRegistry.findAgentByName(targetAgentName);
                if (targetAgent) {
                    receivingAgentNodeId = targetAgent.id;
                    targetHandle = getAgentHandle(targetAgent.type, "input", "right");
                } else {
                    receivingAgentNodeId = currentPhase.orchestratorAgent.id;
                    targetHandle = "orch-right-input-tools";
                }
            }

            // Determine source handle based on whether it's a workflow or a regular tool
            let sourceHandle = `${toolNodeId}-tool-bottom-output`;
            if (stepSource === "LLM") {
                sourceHandle = "llm-bottom-output";
            }

            createTimelineEdge(toolNodeId, receivingAgentNodeId, step, edges, manager, edgeAnimationService, processedSteps, sourceHandle, targetHandle);
        } else {
            console.error(`[Timeline] Could not find source tool node for regular tool result: ${step.id}. Step source (tool name): ${stepSource}.`);
        }
    }
}

function handleAgentResponseText(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    // When step.isSubTaskStep is true, it indicates this is a response from Agent to Orchestrator (as a user)
    if (!currentPhase || step.isSubTaskStep) return;

    const sourceAgentNodeId = currentPhase.orchestratorAgent.id;

    // Always create a new UserNode at the bottom of the chart for each response
    const userNodeInstance = createNewUserNodeAtBottom(manager, currentPhase, step, nodes);

    createTimelineEdge(
        sourceAgentNodeId, // OrchestratorAgent
        userNodeInstance.id, // UserNode
        step,
        edges,
        manager,
        edgeAnimationService,
        processedSteps,
        "orch-bottom-output", // Orchestrator output to user
        "user-top-input" // User input from orchestrator
    );
}

function handleTaskCompleted(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    const parallelFlow = Array.from(manager.parallelFlows.values()).find(p => p.subflowFunctionCallIds.includes(step.functionCallId || ""));

    if (parallelFlow) {
        parallelFlow.completedSubflows.add(step.functionCallId || "");
        if (parallelFlow.completedSubflows.size === parallelFlow.subflowFunctionCallIds.length) {
            // All parallel flows are complete, create a join node
            manager.indentationLevel = 0;
            const newOrchestratorPhase = createNewMainPhase(manager, "OrchestratorAgent", step, nodes);

            // Connect all completed subflows to the new orchestrator node
            currentPhase.subflows.forEach(subflow => {
                if (parallelFlow.subflowFunctionCallIds.includes(subflow.functionCallId)) {
                    createTimelineEdge(subflow.peerAgent.id, newOrchestratorPhase.orchestratorAgent.id, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", "orch-top-input");
                }
            });
            manager.currentSubflowIndex = -1;
        }
        return;
    }

    if (!step.isSubTaskStep) {
        return;
    }

    const subflow = getCurrentSubflow(manager);
    if (!subflow) {
        console.warn(`[Timeline] TASK_COMPLETED with isSubTaskStep=true but no active subflow. Step ID: ${step.id}`);
        return;
    }

    if (!currentPhase) {
        console.error(`[Timeline] No current phase found for TASK_COMPLETED. Step ID: ${step.id}`);
        return;
    }

    const sourcePeerAgent = subflow.peerAgent;

    // Check if an orchestrator node exists anywhere in the flow
    const hasOrchestrator = nodes.some(node => typeof node.data.label === "string" && isOrchestratorAgent(node.data.label));

    let targetNodeId: string;
    let targetHandleId: string;

    if (hasOrchestrator) {
        // Subtask is completing and returning to the orchestrator.
        // Create a new phase for the orchestrator to continue.
        manager.indentationLevel = 0;
        // We need the orchestrator's name. Let's assume it's 'OrchestratorAgent'.
        const newOrchestratorPhase = createNewMainPhase(manager, "OrchestratorAgent", step, nodes);
        targetNodeId = newOrchestratorPhase.orchestratorAgent.id;
        targetHandleId = "orch-top-input";
    } else {
        // No orchestrator found, treat the return as a response to the User.
        const userNodeInstance = createNewUserNodeAtBottom(manager, currentPhase, step, nodes);
        targetNodeId = userNodeInstance.id;
        targetHandleId = "user-top-input";
    }

    createTimelineEdge(sourcePeerAgent.id, targetNodeId, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", targetHandleId);

    manager.currentSubflowIndex = -1;
}

function handleWorkflowExecutionStart(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    // Determine source node
    let sourceNodeId: string;
    let sourceHandle: string;

    const currentSubflow = getCurrentSubflow(manager);
    if (currentSubflow) {
        sourceNodeId = currentSubflow.peerAgent.id;
        sourceHandle = "peer-bottom-output";
    } else {
        sourceNodeId = currentPhase.orchestratorAgent.id;
        sourceHandle = "orch-bottom-output";
    }

    // Attempt to recover functionCallId if missing
    let functionCallIdOverride: string | undefined;
    if (!step.functionCallId && step.owningTaskId) {
        const parentStep = processedSteps.find(s => s.delegationInfo?.some(info => info.subTaskId === step.owningTaskId));
        if (parentStep) {
            const info = parentStep.delegationInfo?.find(i => i.subTaskId === step.owningTaskId);
            if (info) {
                functionCallIdOverride = info.functionCallId;
                console.log(`[Timeline] Recovered functionCallId ${functionCallIdOverride} for workflow ${step.owningTaskId}`);
            }
        }
    }

    // Create workflow context (Group + Agent Node)
    const workflowName = step.data.workflowExecutionStart?.workflowName || "Workflow";
    const workflowContext = startNewWorkflowContext(manager, workflowName, step, nodes, functionCallIdOverride);

    if (workflowContext) {
        // Connect source to workflow agent
        createTimelineEdge(
            sourceNodeId,
            workflowContext.peerAgent.id,
            step,
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            sourceHandle,
            "peer-top-input"
        );
    }
}

function handleWorkflowNodeExecutionStart(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentSubflow = findSubflowBySubTaskId(manager, step.owningTaskId);
    if (!currentSubflow) return;

    // Capture the previous node ID before creating the new one
    let previousNodeId = currentSubflow.lastNodeId;

    // If this is a map iteration, override previousNodeId to be the Map Node
    const parentNodeId = step.data.workflowNodeExecutionStart?.parentNodeId;
    if (parentNodeId) {
        // Find the generated node ID for the parent map node
        // We assume the parent map node was created recently and is in the nodes list
        // We can find it by matching the visualizerStepId or by reconstructing the ID if we knew the counter
        // But simpler: we stored it in mapLayouts!
        // Wait, mapLayouts stores the generated ID? No, it stores the raw ID as key.
        // But we can find the node in `nodes` that corresponds to the parentNodeId.
        // Actually, `createWorkflowNodeInContext` generates IDs like `wf_node_${nodeId}`.
        // So we can reconstruct it.
        // However, `generateNodeId` appends a counter.
        // We need to find the node where data.label or data.description matches?
        // Better: `createWorkflowNodeInContext` should store the generated ID in mapLayouts.
        // Let's assume `wf_node_${parentNodeId}` pattern but we need the exact ID.
        // We can search `nodes` for a node where `data.visualizerStepId` corresponds to the start event of the map node?
        // Or simpler: The Map Node was the `lastNodeId` before any iterations started.
        // But if we have multiple maps, or other nodes...
        // Let's look at `mapLayouts`. We can store the generated `flowNodeId` in `MapLayoutContext`.
        // I'll update `createWorkflowNodeInContext` to do that.
        // Assuming I did that (I didn't in the previous block, let me fix that assumption or logic).
        // Actually, I can find the node by `wf_node_${parentNodeId}` prefix? No, `generateNodeId` uses global counter.
        
        // Let's search for the node in `nodes` that represents the parent map node.
        // The parent map node would have `data.label` or `data.description` containing the ID?
        // Or we can look at `manager.mapLayouts` if we store the generated ID there.
        // I will update `createWorkflowNodeInContext` to store `generatedMapNodeId` in `MapLayoutContext`.
        // Since I can't edit the previous block again in this thought process, I will assume I can find it.
        // Wait, `createWorkflowNodeInContext` is in `taskToFlowData.helpers.ts`. I just edited it.
        // I didn't add `generatedMapNodeId` to `MapLayoutContext`.
        // I can find the node by iterating nodes and checking `data.visualizerStepId`? No, I don't have the parent step ID here.
        
        // Fallback: Iterate nodes to find one where `data.label` or `data.description` matches?
        // Or, since `MapNode` execution happens just before iterations, `currentSubflow.lastNodeId` IS the Map Node!
        // Unless there are multiple maps running in parallel?
        // `DAGExecutor` executes map node, then launches iterations.
        // So `lastNodeId` should be the Map Node.
        // BUT, if we have 2 iterations, for the 2nd iteration, `lastNodeId` is NOT updated (per my change in helpers).
        // So `lastNodeId` remains the Map Node!
        // So `previousNodeId` is correct!
        
        // Verify: `createWorkflowNodeInContext` says:
        // if (!parentNodeId) { subflow.lastNodeId = flowNodeId; }
        // So for iterations, `lastNodeId` is NOT updated.
        // So `previousNodeId` (which is `currentSubflow.lastNodeId`) will point to the node BEFORE the first iteration.
        // Which is the Map Node.
        // So this logic holds.
    }

    // Create the new node
    const newNode = createWorkflowNodeInContext(manager, step, nodes, currentSubflow);

    if (newNode && previousNodeId) {
        // Determine source handle based on previous node type
        const prevNodeObj = nodes.find(n => n.id === previousNodeId);
        let sourceHandle = "peer-bottom-output";
        let edgeLabel: string | undefined;

        if (prevNodeObj?.type === "genericToolNode") {
            sourceHandle = `${previousNodeId}-tool-bottom-output`;
        } else if (prevNodeObj?.type === "llmNode") {
            sourceHandle = "llm-bottom-output";
        } else if (prevNodeObj?.type === "conditionalNode") {
            sourceHandle = "cond-bottom-output";
            // Determine label based on which branch this node represents
            const resultStep = currentSubflow.lastResultStep;
            if (resultStep?.data.workflowNodeExecutionResult?.metadata) {
                const meta = resultStep.data.workflowNodeExecutionResult.metadata;
                const currentNodeId = step.data.workflowNodeExecutionStart?.nodeId;
                if (currentNodeId === meta.selected_branch) {
                    edgeLabel = meta.condition_result ? "True" : "False";
                }
            }
        }

        // Determine target handle based on new node type
        const newNodeObj = nodes.find(n => n.id === newNode.id);
        let targetHandle = "peer-top-input";
        if (newNodeObj?.type === "conditionalNode") {
            targetHandle = "cond-top-input";
        }

        const edge = createTimelineEdge(
            previousNodeId,
            newNode.id,
            currentSubflow.lastResultStep || step, // Use the result of the previous node if available
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            sourceHandle,
            targetHandle
        );

        if (edge && edgeLabel) {
            edge.label = edgeLabel;
        }
    }

    // If this node execution corresponds to a sub-task (agent execution), create a nested subflow context
    // This allows internal events (LLM calls, tools) to be visualized "inside" or attached to this node
    const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
    if (subTaskId && newNode) {
        const currentPhase = getCurrentPhase(manager);
        if (currentPhase) {
            const nestedSubflow: any = {
                id: subTaskId,
                functionCallId: "", // Not triggered by a tool call in the traditional sense
                isParallel: false,
                peerAgent: newNode, // The workflow node acts as the "peer agent" anchor
                groupNode: currentSubflow.groupNode, // Share the same group container
                toolInstances: [],
                currentToolYOffset: 0,
                maxY: currentSubflow.maxY, // Start from current max Y
                maxContentXRelative: currentSubflow.maxContentXRelative,
                callingPhaseId: currentPhase.id,
                parentSubflowId: currentSubflow.id,
                lastNodeId: newNode.id,
            };
            currentPhase.subflows.push(nestedSubflow);
            // We don't switch currentSubflowIndex because we want subsequent workflow nodes
            // to still be added to the main workflow subflow.
            // However, events with this subTaskId will be resolved to this nested subflow
            // by findSubflowBySubTaskId/resolveSubflowContext.
        }
    }
}

function handleWorkflowNodeExecutionResult(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentSubflow = findSubflowBySubTaskId(manager, step.owningTaskId);
    if (!currentSubflow) return;

    // Store this result step so it can be used as the data for the edge connecting to the NEXT node
    currentSubflow.lastResultStep = step;

    const resultData = step.data.workflowNodeExecutionResult;
    const nodeId = resultData?.nodeId;

    // Check if this is a Map Node completing
    if (nodeId && manager.mapLayouts.has(nodeId)) {
        const mapContext = manager.mapLayouts.get(nodeId)!;
        
        // Create a "Join" node (small dot or pill) to bring parallel branches back together
        const joinNodeId = generateNodeId(manager, `join_${nodeId}`);
        
        // Position Join node below the lowest branch
        // We need to find the max Y of all branches.
        // Since we don't track dynamic height of branches easily here without querying nodes,
        // we can estimate or use the current subflow maxY.
        // subflow.maxY should have been updated by the branches growing.
        
        const joinY = currentSubflow.maxY - currentSubflow.groupNode.yPosition + VERTICAL_SPACING;
        
        const joinNode: Node = {
            id: joinNodeId,
            type: "genericAgentNode",
            position: { x: 50, y: joinY }, // Centered relative to group (assuming start node is at 50)
            data: {
                label: "Join",
                visualizerStepId: step.id,
                description: "Map Completion",
                variant: "pill",
            },
            parentId: currentSubflow.groupNode.id,
        };
        
        addNode(nodes, manager.allCreatedNodeIds, joinNode);
        manager.nodePositions.set(joinNodeId, { 
            x: currentSubflow.groupNode.xPosition + 50, 
            y: currentSubflow.groupNode.yPosition + joinY 
        });
        
        // Connect all iteration nodes to the Join node
        mapContext.iterationNodeIds.forEach(iterNodeId => {
            // We need to find the "end" of the iteration branch.
            // If the iteration node had children (tools), we should connect from the last tool.
            // But we don't track the "last node" of each iteration branch easily.
            // However, `shiftNodesVertically` and tool creation logic updates `subflow.lastNodeId`?
            // No, for iterations we explicitly DID NOT update `subflow.lastNodeId`.
            // So `subflow.lastNodeId` is still the Map Node!
            
            // We need to find the last node for each iteration branch.
            // Heuristic: Find the iteration node. Check if it has tools linked to it?
            // The iteration node is an agent node.
            // If it called tools, they are in `subflow.toolInstances`.
            // We can find tools where `parentId` matches the iteration node? No, parentId is group.
            // But we can trace edges?
            
            // Simplification: Connect from the iteration node itself.
            // If there were tools, visually it might look like the line goes through them or overlaps.
            // Ideally, we connect from the bottom-most node in that vertical column.
            
            // Let's just connect from the iteration node for now.
            // If the iteration node expanded (tools), the edge might cross them.
            // To fix this, we would need to track the "tail" of each parallel branch.
            
            createTimelineEdge(
                iterNodeId,
                joinNodeId,
                step,
                edges,
                manager,
                edgeAnimationService,
                processedSteps,
                "peer-bottom-output",
                "peer-top-input"
            );
        });
        
        // Update subflow state so next node connects to Join
        currentSubflow.lastNodeId = joinNodeId;
        
        // Update layout metrics
        currentSubflow.maxY = currentSubflow.groupNode.yPosition + joinY + NODE_HEIGHT;
        manager.nextAvailableGlobalY = currentSubflow.maxY + VERTICAL_SPACING;
        
        // Clean up map context
        manager.mapLayouts.delete(nodeId);
    }

    // Handle visualization of untaken branch for conditional nodes
    if (resultData?.metadata?.condition_result !== undefined) {
        // Find the conditional node
        // lastNodeId points to the node ID (e.g. wf_node_check_risk_7), not the step ID.
        const conditionalNode = nodes.find(n => n.id === currentSubflow.lastNodeId);

        if (conditionalNode && conditionalNode.type === "conditionalNode") {
            const conditionResult = resultData.metadata.condition_result as boolean;

            // Update the conditional node data to include the result for visualization
            const conditionalNodeIndex = nodes.findIndex(n => n.id === conditionalNode.id);
            if (conditionalNodeIndex !== -1) {
                nodes[conditionalNodeIndex] = {
                    ...conditionalNode,
                    data: {
                        ...conditionalNode.data,
                        conditionResult: conditionResult,
                    },
                };
            }

            const trueBranchId = conditionalNode.data.trueBranch as string;
            const falseBranchId = conditionalNode.data.falseBranch as string;

            const untakenBranchId = conditionResult ? falseBranchId : trueBranchId;

            if (untakenBranchId) {
                // Create a "Skipped" node to visualize the untaken path
                const skippedNodeId = generateNodeId(manager, `skipped_${untakenBranchId}`);

                let label = untakenBranchId;
                const cData = conditionalNode.data as any;
                if (untakenBranchId === cData.trueBranch && cData.trueBranchLabel) {
                    label = cData.trueBranchLabel;
                } else if (untakenBranchId === cData.falseBranch && cData.falseBranchLabel) {
                    label = cData.falseBranchLabel;
                }

                const skippedNode: Node = {
                    id: skippedNodeId,
                    type: "genericAgentNode",
                    position: {
                        x: conditionalNode.position.x + 200, // Position to the right
                        y: conditionalNode.position.y, // Same Y level
                    },
                    data: {
                        label: label,
                        description: `Untaken branch`,
                        variant: "pill",
                    },
                    parentId: currentSubflow.groupNode.id,
                    style: { opacity: 0.5, borderStyle: "dashed" },
                };

                addNode(nodes, manager.allCreatedNodeIds, skippedNode);
                manager.nodePositions.set(skippedNodeId, {
                    x: (currentSubflow.groupNode.xPosition || 0) + skippedNode.position.x,
                    y: (currentSubflow.groupNode.yPosition || 0) + skippedNode.position.y
                });

                // Expand group width if needed
                const requiredWidth = skippedNode.position.x + 150 + GROUP_PADDING_X;

                // Update maxContentXRelative to ensure final pass respects this width
                currentSubflow.maxContentXRelative = Math.max(currentSubflow.maxContentXRelative, skippedNode.position.x + 150);

                if (requiredWidth > (currentSubflow.groupNode.width || 0)) {
                    currentSubflow.groupNode.width = requiredWidth;
                    const groupNode = nodes.find(n => n.id === currentSubflow.groupNode.id);
                    if (groupNode) {
                        groupNode.style = { ...groupNode.style, width: `${requiredWidth}px` };
                    }
                }

                // Draw dashed edge to skipped node
                const edge = createTimelineEdge(
                    conditionalNode.id,
                    skippedNodeId,
                    step,
                    edges,
                    manager,
                    edgeAnimationService,
                    processedSteps,
                    "cond-right-output",
                    "peer-left-input"
                );

                if (edge) {
                    edge.label = conditionResult ? "False" : "True";
                    edge.style = { ...edge.style, strokeDasharray: "5,5", opacity: 0.5 };
                }
            }
        }
    }
}

function handleWorkflowExecutionResult(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[], edgeAnimationService: EdgeAnimationService, processedSteps: VisualizerStep[]): void {
    const currentSubflow = findSubflowBySubTaskId(manager, step.owningTaskId);
    if (!currentSubflow) return;

    // Create Finish Node
    const finishNodeId = generateNodeId(manager, `finish_${currentSubflow.id}`);

    // Calculate relative Y position for Finish node based on current content height
    // Add VERTICAL_SPACING to ensure consistent gap after the last node
    let relativeY = currentSubflow.maxY - currentSubflow.groupNode.yPosition + VERTICAL_SPACING;

    // Safety check: Ensure relativeY is strictly below the last node
    if (currentSubflow.lastNodeId) {
        const lastNode = nodes.find(n => n.id === currentSubflow.lastNodeId);
        if (lastNode) {
            // Use estimated height if not available
            const lastNodeHeight = (lastNode.measured?.height) || NODE_HEIGHT;
            const lastNodeBottom = lastNode.position.y + lastNodeHeight;
            relativeY = Math.max(relativeY, lastNodeBottom + VERTICAL_SPACING);
        }
    }

    const finishNode: Node = {
        id: finishNodeId,
        type: "genericAgentNode",
        position: {
            x: 50,
            y: relativeY,
        },
        data: {
            label: "Finish",
            visualizerStepId: step.id,
            description: "Workflow Completion",
            variant: "pill",
        },
        parentId: currentSubflow.groupNode.id,
    };

    addNode(nodes, manager.allCreatedNodeIds, finishNode);
    manager.nodePositions.set(finishNodeId, finishNode.position);

    // Store finishNodeId in context for later use by handleToolExecutionResult
    currentSubflow.finishNodeId = finishNodeId;

    // Connect last node to Finish node
    if (currentSubflow.lastNodeId) {
        // Determine source handle for last node
        // If last node was a tool, use tool handle. If it was an agent (Start node), use peer handle.
        const lastNode = nodes.find(n => n.id === currentSubflow.lastNodeId);
        let sourceHandle = "peer-bottom-output";
        if (lastNode?.type === "genericToolNode" || lastNode?.type === "llmNode") {
            sourceHandle = `${currentSubflow.lastNodeId}-tool-bottom-output`;
            if (lastNode.type === "llmNode") sourceHandle = "llm-bottom-output";
        }

        createTimelineEdge(
            currentSubflow.lastNodeId,
            finishNodeId,
            currentSubflow.lastResultStep || step, // Use the result of the last node if available
            edges,
            manager,
            edgeAnimationService,
            processedSteps,
            sourceHandle,
            "peer-top-input"
        );
    }

    // Update layout metrics
    // The finish node is at relativeY. Its bottom is relativeY + NODE_HEIGHT.
    // We want the group to extend to relativeY + NODE_HEIGHT + GROUP_PADDING_Y.
    const finishNodeBottomRelative = relativeY + NODE_HEIGHT;
    const requiredGroupHeight = finishNodeBottomRelative + GROUP_PADDING_Y;

    // Update subflow.maxY to reflect the finish node (absolute Y)
    currentSubflow.maxY = currentSubflow.groupNode.yPosition + finishNodeBottomRelative;

    // Update group height
    const groupNodeData = nodes.find(n => n.id === currentSubflow.groupNode.id);
    if (groupNodeData && groupNodeData.style) {
        groupNodeData.style.height = `${requiredGroupHeight}px`;
    }
    
    // Update global Y tracker
    manager.nextAvailableGlobalY = currentSubflow.maxY + VERTICAL_SPACING;
}

function handleTaskFailed(step: VisualizerStep, manager: TimelineLayoutManager, nodes: Node[], edges: Edge[]): void {
    const currentPhase = getCurrentPhase(manager);
    if (!currentPhase) return;

    const sourceName = step.source || "UnknownSource";
    const targetName = step.target || "User";

    // Find the last agent node from the agents in current phase that matches the source
    let sourceAgentNode: NodeInstance | undefined;
    let sourceHandle = "orch-bottom-output"; // Default handle

    // Check if source is in current subflow
    const currentSubflow = getCurrentSubflow(manager);
    if (currentSubflow && currentSubflow.peerAgent.id.includes(sourceName.replace(/[^a-zA-Z0-9_]/g, "_"))) {
        sourceAgentNode = currentSubflow.peerAgent;
        sourceHandle = "peer-bottom-output";
    } else {
        // Check if source matches orchestrator agent
        if (currentPhase.orchestratorAgent.id.includes(sourceName.replace(/[^a-zA-Z0-9_]/g, "_"))) {
            sourceAgentNode = currentPhase.orchestratorAgent;
            sourceHandle = "orch-bottom-output";
        } else {
            // Look for any peer agent in subflows that matches the source
            for (const subflow of currentPhase.subflows) {
                if (subflow.peerAgent.id.includes(sourceName.replace(/[^a-zA-Z0-9_]/g, "_"))) {
                    sourceAgentNode = subflow.peerAgent;
                    sourceHandle = "peer-bottom-output";
                    break;
                }
            }
        }
    }

    if (!sourceAgentNode) {
        // Fallback: If we can't find a matching source agent, use the orchestrator agent from the current phase
        // This handles cases where the task fails before any agent activity (e.g., early validation errors)
        console.warn(`[Timeline] Could not find source agent node for TASK_FAILED: ${sourceName}. Using orchestrator agent as fallback.`);
        if (currentPhase.orchestratorAgent) {
            sourceAgentNode = currentPhase.orchestratorAgent;
            sourceHandle = "orch-bottom-output";
        } else {
            console.error(`[Timeline] No orchestrator agent available in current phase for TASK_FAILED`);
            return;
        }
    }

    // Create a new target node with error state
    let targetNodeId: string;
    let targetHandleId: string;

    if (isOrchestratorAgent(targetName)) {
        // Create a new orchestrator phase for error handling
        manager.indentationLevel = 0;
        const newOrchestratorPhase = createNewMainPhase(manager, targetName, step, nodes);

        targetNodeId = newOrchestratorPhase.orchestratorAgent.id;
        targetHandleId = "orch-top-input";
        manager.currentSubflowIndex = -1;
    } else {
        // Create a new user node at the bottom for error notification
        const userNodeInstance = createNewUserNodeAtBottom(manager, currentPhase, step, nodes);

        targetNodeId = userNodeInstance.id;
        targetHandleId = "user-top-input";
    }

    // Create an error edge (red color) between source and target
    createErrorEdge(sourceAgentNode.id, targetNodeId, step, edges, manager, sourceHandle, targetHandleId);
}

// Helper function to create error edges with error state data
function createErrorEdge(sourceNodeId: string, targetNodeId: string, step: VisualizerStep, edges: Edge[], manager: TimelineLayoutManager, sourceHandleId?: string, targetHandleId?: string): void {
    if (!sourceNodeId || !targetNodeId || sourceNodeId === targetNodeId) {
        return;
    }

    // Validate that source and target nodes exist
    const sourceExists = manager.allCreatedNodeIds.has(sourceNodeId);
    const targetExists = manager.allCreatedNodeIds.has(targetNodeId);

    if (!sourceExists || !targetExists) {
        return;
    }

    const edgeId = `error-edge-${sourceNodeId}${sourceHandleId || ""}-to-${targetNodeId}${targetHandleId || ""}-${step.id}`;

    const edgeExists = edges.some(e => e.id === edgeId);

    if (!edgeExists) {
        const errorMessage = step.data.errorDetails?.message || "Task failed";
        const label = errorMessage.length > 30 ? "Error" : errorMessage;

        const newEdge: Edge = {
            id: edgeId,
            source: sourceNodeId,
            target: targetNodeId,
            label: label,
            type: "defaultFlowEdge",
            data: {
                visualizerStepId: step.id,
                isAnimated: false,
                animationType: "static",
                isError: true,
                errorMessage: errorMessage,
            } as unknown as Record<string, unknown>,
        };

        // Only add handles if they are provided and valid
        if (sourceHandleId) {
            newEdge.sourceHandle = sourceHandleId;
        }
        if (targetHandleId) {
            newEdge.targetHandle = targetHandleId;
        }

        edges.push(newEdge);
    }
}

// Main transformation function
export const transformProcessedStepsToTimelineFlow = (processedSteps: VisualizerStep[], agentNameMap: Record<string, string> = {}): FlowData => {
    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    if (!processedSteps || processedSteps.length === 0) {
        return { nodes: newNodes, edges: newEdges };
    }

    // Initialize edge animation service
    const edgeAnimationService = new EdgeAnimationService();

    const manager: TimelineLayoutManager = {
        phases: [],
        currentPhaseIndex: -1,
        currentSubflowIndex: -1,
        parallelFlows: new Map(),
        nextAvailableGlobalY: Y_START,
        nodeIdCounter: 0,
        allCreatedNodeIds: new Set(),
        nodePositions: new Map(),
        allUserNodes: [],
        userNodeCounter: 0,
        agentRegistry: createAgentRegistry(),
        indentationLevel: 0,
        indentationStep: 50, // Pixels to indent per level
        agentNameMap: agentNameMap,
        mapLayouts: new Map(),
    };

    const filteredSteps = processedSteps.filter(step => RELEVANT_STEP_TYPES.includes(step.type));

    // Ensure the first USER_REQUEST step is processed first
    const firstUserRequestIndex = filteredSteps.findIndex(step => step.type === "USER_REQUEST");
    let reorderedSteps = filteredSteps;

    if (firstUserRequestIndex > 0) {
        // Move the first USER_REQUEST to the beginning
        const firstUserRequest = filteredSteps[firstUserRequestIndex];
        reorderedSteps = [firstUserRequest, ...filteredSteps.slice(0, firstUserRequestIndex), ...filteredSteps.slice(firstUserRequestIndex + 1)];
    }

    for (const step of reorderedSteps) {
        // Special handling for AGENT_LLM_RESPONSE_TOOL_DECISION if it's a peer delegation trigger
        // This step often precedes AGENT_TOOL_INVOCATION_START for peers.
        // The plan implies AGENT_TOOL_INVOCATION_START is the primary trigger for peer delegation.
        // For now, we rely on AGENT_TOOL_INVOCATION_START to have enough info.

        switch (step.type) {
            case "USER_REQUEST":
                handleUserRequest(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "AGENT_LLM_CALL":
                handleLLMCall(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "AGENT_LLM_RESPONSE_TO_AGENT":
            case "AGENT_LLM_RESPONSE_TOOL_DECISION":
                handleLLMResponseToAgent(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "AGENT_TOOL_INVOCATION_START":
                handleToolInvocationStart(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "AGENT_TOOL_EXECUTION_RESULT":
                handleToolExecutionResult(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "AGENT_RESPONSE_TEXT":
                handleAgentResponseText(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "TASK_COMPLETED":
                handleTaskCompleted(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "TASK_FAILED":
                handleTaskFailed(step, manager, newNodes, newEdges);
                break;
            case "WORKFLOW_EXECUTION_START":
                handleWorkflowExecutionStart(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "WORKFLOW_NODE_EXECUTION_START":
                handleWorkflowNodeExecutionStart(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "WORKFLOW_NODE_EXECUTION_RESULT":
                handleWorkflowNodeExecutionResult(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
            case "WORKFLOW_EXECUTION_RESULT":
                handleWorkflowExecutionResult(step, manager, newNodes, newEdges, edgeAnimationService, processedSteps);
                break;
        }
    }

    // Update group node heights based on final maxYInSubflow
    manager.phases.forEach(phase => {
        phase.subflows.forEach(subflow => {
            const groupNodeData = newNodes.find(n => n.id === subflow.groupNode.id);
            if (groupNodeData && groupNodeData.style) {
                // Update Height
                // peerAgent.yPosition is absolute, subflow.maxY is absolute.
                // groupNode.yPosition is absolute.
                // Content height is from top of first element (peerAgent) to bottom of last element in subflow.
                // Relative Y of peer agent is GROUP_PADDING_Y.
                // Max Y of content relative to group top = subflow.maxY - subflow.groupNode.yPosition
                const contentMaxYRelative = subflow.maxY - subflow.groupNode.yPosition;
                const requiredGroupHeight = contentMaxYRelative + GROUP_PADDING_Y; // Add bottom padding
                
                // Ensure we don't shrink the group if it was already set larger (e.g. by handleWorkflowExecutionResult)
                const currentHeight = parseInt(groupNodeData.style.height?.toString().replace("px", "") || "0");
                groupNodeData.style.height = `${Math.max(NODE_HEIGHT + 2 * GROUP_PADDING_Y, requiredGroupHeight, currentHeight)}px`;

                // Update Width
                // Ensure the group width is sufficient to contain all indented tool nodes
                const requiredGroupWidth = subflow.maxContentXRelative + GROUP_PADDING_X;

                groupNodeData.style.width = `${requiredGroupWidth}px`;
            }
        });
    });

    return { nodes: newNodes, edges: newEdges };
};
