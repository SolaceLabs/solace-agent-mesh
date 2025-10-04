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
    resolveSubflowContext,
    isParallelFlow,
    findToolInstanceByNameEnhanced,
    createNewMainPhase,
    startNewSubflow,
    createNewToolNodeInContext,
    createTimelineEdge,
    createNewUserNodeAtBottom,
    createAgentRegistry,
    getAgentHandle,
    isOrchestratorAgent,
} from "./taskToFlowData.helpers";
import { EdgeAnimationService } from "./edgeAnimationService";

// Relevant step types that should be processed in the flow chart
const RELEVANT_STEP_TYPES = ["USER_REQUEST", "AGENT_LLM_CALL", "AGENT_LLM_RESPONSE_TO_AGENT", "AGENT_LLM_RESPONSE_TOOL_DECISION", "AGENT_TOOL_INVOCATION_START", "AGENT_TOOL_EXECUTION_RESULT", "AGENT_RESPONSE_TEXT", "TASK_COMPLETED", "TASK_FAILED"];

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
    const targetAgentName = step.target || "OrchestratorAgent";

    if (step.data.toolResult?.isPeerResponse) {
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
                createTimelineEdge(
                    subflow.lastSubflow?.peerAgent.id ?? subflow.peerAgent.id,
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

        // If we reach here, it's a NON-PARALLEL (sequential) peer return.
        const sourceAgent = manager.agentRegistry.findAgentByName(stepSource.startsWith("peer_") ? stepSource.substring(5) : stepSource);
        if (!sourceAgent) {
            console.error(`[Timeline] Source peer agent not found for peer response: ${stepSource}.`);
            return;
        }

        if (isOrchestratorAgent(targetAgentName)) {
            manager.indentationLevel = 0;
            const newOrchestratorPhase = createNewMainPhase(manager, targetAgentName, step, nodes);
            createTimelineEdge(sourceAgent.id, newOrchestratorPhase.orchestratorAgent.id, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", "orch-top-input");
            manager.currentSubflowIndex = -1;
        } else {
            // Peer-to-peer sequential return.
            manager.indentationLevel = Math.max(0, manager.indentationLevel - 1);

            // Check if we need to consider parallel flow context for this return
            const isWithinParallelContext = isParallelFlow(step, manager) || Array.from(manager.parallelFlows.values()).some(pf => pf.subflowFunctionCallIds.some(id => currentPhase.subflows.some(sf => sf.functionCallId === id)));

            const newSubflow = startNewSubflow(manager, targetAgentName, step, nodes, isWithinParallelContext);
            if (newSubflow) {
                createTimelineEdge(sourceAgent.id, newSubflow.peerAgent.id, step, edges, manager, edgeAnimationService, processedSteps, "peer-bottom-output", "peer-top-input");
            }
        }
    } else {
        // Regular tool (non-peer) returning result
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

            createTimelineEdge(toolNodeId, receivingAgentNodeId, step, edges, manager, edgeAnimationService, processedSteps, stepSource === "LLM" ? "llm-bottom-output" : `${toolNodeId}-tool-bottom-output`, targetHandle);
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
        console.error(`[Timeline] Could not find source agent node for TASK_FAILED: ${sourceName}`);
        return;
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
                groupNodeData.style.height = `${Math.max(NODE_HEIGHT + 2 * GROUP_PADDING_Y, requiredGroupHeight)}px`;

                // Update Width
                // Ensure the group width is sufficient to contain all indented tool nodes
                const requiredGroupWidth = subflow.maxContentXRelative + GROUP_PADDING_X;

                // Add extra padding to ensure the group is wide enough for indented tools
                const minRequiredWidth = NODE_WIDTH + 2 * GROUP_PADDING_X + manager.indentationLevel * manager.indentationStep;

                groupNodeData.style.width = `${Math.max(requiredGroupWidth, minRequiredWidth)}px`;
            }
        });
    });

    return { nodes: newNodes, edges: newEdges };
};
