import type { VisualizerStep } from "@/lib/types";
import { LayoutBlock, VerticalStackBlock, LeafBlock, GroupBlock, HorizontalStackBlock } from "./LayoutBlock";
import { VERTICAL_SPACING, NODE_HEIGHT } from "./constants";
import type { Node, Edge } from "@xyflow/react";

/**
 * Responsible for converting a linear stream of VisualizerSteps into a hierarchical LayoutBlock tree.
 */
export class BlockBuilder {
    private root: VerticalStackBlock;
    private nodeCounter: number = 0;
    private groupCounter: number = 0;

    private edges: Edge[] = [];
    private lastNodeId: string | null = null;
    private lastNodeBlock: LayoutBlock | null = null;
    private lastNodeByTaskId: Map<string, string> = new Map();
    private agentNameMap: Record<string, string>;
    private yamlNodeIdToGeneratedId: Map<string, string> = new Map();

    // Map to track container blocks by task ID (for Agents/User nodes)
    private taskBlockMap: Map<string, LayoutBlock> = new Map();

    // Map to track tool stack blocks by task ID (for Tools/Sub-agents)
    private taskToolStackMap: Map<string, VerticalStackBlock> = new Map();

    // Map to track the single user response node per task
    private taskUserResponseNodeMap: Map<string, LeafBlock> = new Map();

    constructor(agentNameMap: Record<string, string> = {}) {
        this.root = new VerticalStackBlock("root");
        this.agentNameMap = agentNameMap;
    }

    public build(steps: VisualizerStep[]): { root: LayoutBlock, edges: Edge[] } {
        // console.log(`[BlockBuilder] Building flow from ${steps.length} steps.`);
        for (const step of steps) {
            this.processStep(step);
        }
        return { root: this.root, edges: this.edges };
    }

    private getBlockForTask(taskId: string): LayoutBlock {
        const block = this.taskBlockMap.get(taskId);
        if (!block) {
            // console.log(`[BlockBuilder] No block found for task '${taskId}', defaulting to root.`);
            return this.root;
        }
        return block;
    }

    private processStep(step: VisualizerStep) {
        // console.log(`[BlockBuilder] Processing step: ${step.type} (${step.id})`);
        switch (step.type) {
            case "USER_REQUEST":
                this.handleUserRequest(step);
                break;
            case "AGENT_LLM_CALL":
                this.handleLLMCall(step);
                break;
            case "AGENT_LLM_RESPONSE_TO_AGENT":
            case "AGENT_LLM_RESPONSE_TOOL_DECISION":
                this.handleLLMResponse(step);
                break;
            case "AGENT_TOOL_INVOCATION_START":
                this.handleToolInvocation(step);
                break;
            case "AGENT_TOOL_EXECUTION_RESULT":
                this.handleToolResult(step);
                break;
            case "AGENT_RESPONSE_TEXT":
                this.handleAgentResponse(step);
                break;
            case "TASK_COMPLETED":
                this.handleTaskCompleted(step);
                break;
            case "WORKFLOW_EXECUTION_START":
                {
                    const wfName = step.data.workflowExecutionStart?.workflowName || "Workflow";
                    const displayName = this.agentNameMap[wfName] || wfName;
                    this.startGroup("workflow", step, displayName);
                }
                break;
            case "WORKFLOW_EXECUTION_RESULT":
                this.handleWorkflowExecutionResult(step);
                break;
            case "WORKFLOW_NODE_EXECUTION_START":
                this.handleWorkflowNodeStart(step);
                break;
            case "WORKFLOW_NODE_EXECUTION_RESULT":
                this.handleWorkflowNodeResult(step);
                break;
        }
    }

    private handleUserRequest(step: VisualizerStep) {
        // 1. Add User Node (Top)
        this.addNode("userNode", step, "User", { isTopNode: true }, step.owningTaskId);

        // 2. Add Agent Node immediately (formerly Orchestrator)
        const agentName = step.target || "Agent";
        const displayName = this.agentNameMap[agentName] || agentName;
        this.addNode("genericAgentNode", step, displayName, {}, step.owningTaskId);
    }

    private handleLLMCall(step: VisualizerStep) {
        const taskId = step.owningTaskId;
        const container = this.getBlockForTask(taskId);
        const agentBlock = this.findActiveAgentNode(container);
        const sourceId = agentBlock ? agentBlock.id : undefined;

        this.addNode("llmNode", step, "LLM", {}, taskId, true, sourceId, agentBlock || undefined);
    }

    private handleLLMResponse(step: VisualizerStep) {
        const taskId = step.owningTaskId;

        // Try to find the tool stack first, as that's where tools/LLMs live
        // If not found, fallback to the main task block (e.g. for simple flows)
        let container = this.taskToolStackMap.get(taskId);
        if (!container) {
            container = this.getBlockForTask(taskId) as VerticalStackBlock;
        }

        // Find the active agent node (Orchestrator or Peer) in this container
        const agentBlock = this.findActiveAgentNode(container);

        // Find the last tool/LLM node to connect back from
        const toolBlock = this.findLastToolOrLLMNode(container);

        if (agentBlock && toolBlock) {
            const toolId = toolBlock.id;

            // Create return edge from Tool/LLM back to Agent
            const targetHandle = `agent-in-${toolId}`;

            let sourceHandle = "peer-bottom-output";
            if (toolId.startsWith("llmNode")) {
                sourceHandle = "llm-bottom-output";
            } else if (toolId.startsWith("genericToolNode")) {
                sourceHandle = `${toolId}-tool-bottom-output`;
            }

            this.createEdge(toolId, agentBlock.id, step.id, sourceHandle, targetHandle);

            // Reset lastNodeId to the Agent
            this.lastNodeId = agentBlock.id;
            this.lastNodeBlock = agentBlock;

            // Update task tracking so next node connects to Agent
            if (taskId) {
                this.lastNodeByTaskId.set(taskId, agentBlock.id);
            }
        }
    }

    private findLastToolOrLLMNode(container: LayoutBlock): LayoutBlock | null {
        // Search backwards in the current block (ToolsStack)
        for (let i = container.children.length - 1; i >= 0; i--) {
            const block = container.children[i];
            if (block.nodePayload) {
                const type = block.nodePayload.type;
                if (type === "llmNode" || type === "genericToolNode") {
                    return block;
                }
            }
        }
        return null;
    }

    private handleAgentResponse(step: VisualizerStep) {
        // Only create User response nodes for the top-level task (nestingLevel 0)
        if (step.nestingLevel > 0) {
            return;
        }

        const taskId = step.owningTaskId;

        // Check if we already have a user response node for this task
        let userNode = this.taskUserResponseNodeMap.get(taskId);

        if (userNode) {
            return;
        }

        // Create new User Node if not exists
        // Ensure we connect from the Orchestrator/Agent
        const container = this.getBlockForTask(taskId);
        const agentBlock = this.findActiveAgentNode(container);
        const explicitSourceId = agentBlock ? agentBlock.id : undefined;

        const nodeId = this.addNode("userNode", step, "User", { isBottomNode: true }, taskId, true, explicitSourceId, agentBlock || undefined);

        // Register this node as the response node for this task
        // We need to find the block we just created.
        // addNode adds it to the container.
        const newNodeBlock = container.children[container.children.length - 1] as LeafBlock;
        if (newNodeBlock && newNodeBlock.id === nodeId) {
            this.taskUserResponseNodeMap.set(taskId, newNodeBlock);
        }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private addNode(type: string, step: VisualizerStep, label: string, data: any = {}, targetTaskId: string, connectToLast: boolean = true, explicitSourceId?: string, explicitSourceBlock?: LayoutBlock, explicitContainer?: LayoutBlock): string {
        const nodeId = `${type}_${this.nodeCounter++}`;
        console.log(`[BlockBuilder] Adding node '${nodeId}' (${type}: ${label}) for task '${targetTaskId}'`);

        const node: Node = {
            id: nodeId,
            type: type,
            position: { x: 0, y: 0 }, // Will be set by layout engine
            data: { label: label, visualizerStepId: step.id, ...data }
        };
        const block = new LeafBlock(nodeId, node);

        // Determine container based on node type and task ID
        let container: LayoutBlock;

        if (explicitContainer) {
            container = explicitContainer;
        } else if (type === "orchestratorNode" || type === "genericAgentNode") {
            // Agents start a new Interaction Row
            // They are added to the main flow container (Root or parent ToolStack)
            container = this.getBlockForTask(targetTaskId);
        } else if (type === "userNode") {
            // User nodes go to the main flow container
            container = this.getBlockForTask(targetTaskId);
        } else {
            // Tools, LLMs, etc. go to the Tools Stack
            const toolStack = this.taskToolStackMap.get(targetTaskId);
            if (toolStack) {
                container = toolStack;
            } else {
                console.log(`[BlockBuilder] Tool stack not found for task '${targetTaskId}'. Fallback to main container.`);
                // Fallback to main container if no tool stack found
                container = this.getBlockForTask(targetTaskId);
            }
        }

        if (type === "orchestratorNode" || type === "genericAgentNode") {
            const rowId = `row_${nodeId}`;
            const rowBlock = new HorizontalStackBlock(rowId);

            // Add Agent to Row
            rowBlock.addChild(block);

            // Create Tools Stack
            const toolsStackId = `tools_${nodeId}`;
            const toolsStack = new VerticalStackBlock(toolsStackId);
            rowBlock.addChild(toolsStack);

            // Add Row to Container
            container.addChild(rowBlock);

            // Register Tools Stack as the container for tools of this task
            console.log(`[BlockBuilder] Registering tool stack for task '${targetTaskId}': ${toolsStackId}`);
            this.taskToolStackMap.set(targetTaskId, toolsStack);
        } else {
            container.addChild(block);
        }

        // Determine source node for edge
        let sourceNodeId = explicitSourceId || this.lastNodeId;
        let sourceType = "";

        // Check if we are the first node in the current block and if the block has an anchor
        if (!explicitSourceId && container.children.length === 1 && container.anchorNodeId) {
            sourceNodeId = container.anchorNodeId;
            sourceType = "genericAgentNode";
        }
        // Otherwise, check task-specific history for sequential flow
        else if (!explicitSourceId && targetTaskId && this.lastNodeByTaskId.has(targetTaskId)) {
            sourceNodeId = this.lastNodeByTaskId.get(targetTaskId)!;
            sourceType = sourceNodeId.split("_")[0];
        } else if (sourceNodeId) {
            sourceType = sourceNodeId.split("_")[0];
        }

        // Special handling for Agent -> Tool/LLM connections to use dynamic slots
        let customSourceHandle: string | undefined;
        let customTargetHandle: string | undefined;

        if (connectToLast && sourceNodeId && (type === "llmNode" || type === "genericToolNode")) {
            // If source is an agent, add a tool slot
            if (sourceType === "orchestratorNode" || sourceType === "genericAgentNode") {
                // We need to update the agent node data to render handles
                // We don't need to calculate yOffset for layout anymore, but we need it for handle positioning

                // Find the source node object
                let sourceBlock = explicitSourceBlock;
                if (!sourceBlock && this.lastNodeBlock?.id === sourceNodeId) {
                    sourceBlock = this.lastNodeBlock;
                }

                if (sourceBlock && sourceBlock.nodePayload) {
                    // We have the block.
                    const agentNode = sourceBlock.nodePayload;
                    if (!agentNode.data.toolSlots) agentNode.data.toolSlots = [];

                    // Estimate offset for handle
                    const slotIndex = (agentNode.data.toolSlots as any[]).length;
                    const toolPitch = NODE_HEIGHT + (VERTICAL_SPACING / 2);
                    const initialOffset = 25;
                    const yOffset = initialOffset + (slotIndex * toolPitch);

                    (agentNode.data.toolSlots as any[]).push({ id: nodeId, yOffset });

                    customSourceHandle = `agent-out-${nodeId}`;
                    customTargetHandle = type === "llmNode" ? "llm-left-input" : `${nodeId}-tool-left-input`;
                } else {
                    // Fallback: we can't find it easily.
                    // But we need to set the edge handles.
                    customSourceHandle = `agent-out-${nodeId}`;
                    customTargetHandle = type === "llmNode" ? "llm-left-input" : `${nodeId}-tool-left-input`;
                }
            }
        }

        // Create edge
        if (connectToLast && sourceNodeId) {
            let { sourceHandle, targetHandle } = this.resolveHandles(sourceType, type, sourceNodeId, nodeId);

            if (customSourceHandle) sourceHandle = customSourceHandle;
            if (customTargetHandle) targetHandle = customTargetHandle;

            this.createEdge(sourceNodeId, nodeId, step.id, sourceHandle, targetHandle);
        }

        // Update tracking
        this.lastNodeId = nodeId;
        this.lastNodeBlock = block;
        if (targetTaskId) {
            this.lastNodeByTaskId.set(targetTaskId, nodeId);
        }

        return nodeId;
    }

    private findActiveAgentNode(container: LayoutBlock): LayoutBlock | null {
        // In the new nested model, the container is likely the ToolsStack.
        // The Agent is the first child of the parent InteractionRow.
        if (container.parent instanceof HorizontalStackBlock) {
            const row = container.parent;
            if (row.children.length > 0 && row.children[0] instanceof LeafBlock) {
                const potentialAgent = row.children[0];
                if (potentialAgent.nodePayload?.type === "orchestratorNode" || potentialAgent.nodePayload?.type === "genericAgentNode") {
                    return potentialAgent;
                }
            }
        } else {
            // console.log(`[BlockBuilder] findActiveAgentNode: container parent is not HorizontalStackBlock. Parent type: ${container.parent?.constructor.name}`);
        }

        // Fallback for flat structures (e.g. root)
        for (let i = container.children.length - 1; i >= 0; i--) {
            const block = container.children[i];
            if (block.nodePayload) {
                const type = block.nodePayload.type;
                if (type === "orchestratorNode" || type === "genericAgentNode") {
                    return block;
                }
            }
            // Check if block is a row containing an agent (for root container)
            if (block instanceof HorizontalStackBlock && block.children.length > 0) {
                const firstChild = block.children[0];
                if (firstChild instanceof LeafBlock && firstChild.nodePayload) {
                    const type = firstChild.nodePayload.type;
                    if (type === "orchestratorNode" || type === "genericAgentNode") {
                        return firstChild;
                    }
                }
            }
        }
        return null;
    }

    private resolveHandles(sourceType: string, targetType: string, sourceId: string, targetId: string): { sourceHandle?: string, targetHandle?: string } {
        let sourceHandle: string | undefined;
        let targetHandle: string | undefined;

        // Source Handle
        switch (sourceType) {
            case "userNode":
                sourceHandle = "user-bottom-output";
                break;
            case "orchestratorNode":
                sourceHandle = "orch-bottom-output";
                break;
            case "genericAgentNode":
                sourceHandle = "peer-bottom-output";
                break;
            case "llmNode":
                sourceHandle = "llm-bottom-output";
                break;
            case "genericToolNode":
                sourceHandle = `${sourceId}-tool-bottom-output`;
                break;
            case "conditionalNode":
                sourceHandle = "cond-bottom-output";
                break;
        }

        // Target Handle
        switch (targetType) {
            case "userNode":
                targetHandle = "user-top-input";
                break;
            case "orchestratorNode":
                targetHandle = "orch-top-input";
                break;
            case "genericAgentNode":
                targetHandle = "peer-top-input";
                break;
            case "llmNode":
                targetHandle = "llm-left-input";
                break;
            case "genericToolNode":
                targetHandle = `${targetId}-tool-left-input`;
                break;
            case "conditionalNode":
                targetHandle = "cond-top-input";
                break;
        }

        return { sourceHandle, targetHandle };
    }

    private createEdge(source: string, target: string, stepId?: string, sourceHandle?: string, targetHandle?: string) {
        const edgeId = `e_${source}_${target}`;

        // Avoid duplicates
        if (this.edges.some(e => e.id === edgeId)) {
            return;
        }

        console.log(`[BlockBuilder] Creating edge ${source} -> ${target} (step: ${stepId})`);
        const edge: Edge = {
            id: edgeId,
            source: source,
            target: target,
            type: "defaultFlowEdge",
            animated: true,
            data: {
                visualizerStepId: stepId
            }
        };

        if (sourceHandle) edge.sourceHandle = sourceHandle;
        if (targetHandle) edge.targetHandle = targetHandle;

        this.edges.push(edge);
    }

    private startGroup(type: string, step: VisualizerStep, label: string) {
        const groupId = `group_${this.groupCounter++}`;
        console.log(`[BlockBuilder] Starting group '${groupId}' (${type}: ${label}) for parent task '${step.owningTaskId}'`);

        // Only show label for workflows, hide for sub-agents
        const groupLabel = type === "workflow" ? label : "";

        const groupNode: Node = {
            id: groupId,
            type: "group",
            position: { x: 0, y: 0 },
            data: { 
                label: groupLabel,
                functionCallId: step.functionCallId // Store functionCallId for correlation
            },
            style: {
                width: 0,
                height: 0,
                backgroundColor: "rgba(220, 220, 255, 0.1)",
                border: "1px solid #aac",
                borderRadius: "8px",
            }
        };

        const groupBlock = new GroupBlock(groupId, groupNode);

        // Reduce padding for sub-agent groups since they don't have a label
        if (type === "subflow") {
            groupBlock.paddingY = 20;
        }

        // Determine where to add the group
        let parentContainer: LayoutBlock;
        if (type === "subflow") {
            // Subflows go into the tool stack of the parent task
            const parentTaskId = step.owningTaskId;
            const toolStack = this.taskToolStackMap.get(parentTaskId);
            parentContainer = toolStack || this.getBlockForTask(parentTaskId);
        } else {
            // Workflows go into the main flow of their PARENT task (the caller)
            // If parentTaskId is available, use it. Otherwise fallback to owningTaskId (which might be root)
            const containerTaskId = step.parentTaskId;
            
            if (containerTaskId) {
                // If we have a parent task, we want to be in its tool stack (like a subflow)
                // This ensures the workflow is nested under the calling agent
                const toolStack = this.taskToolStackMap.get(containerTaskId);
                parentContainer = toolStack || this.getBlockForTask(containerTaskId);
            } else {
                // Fallback to owning task (root) if no parent
                parentContainer = this.getBlockForTask(step.owningTaskId);
            }
        }

        parentContainer.addChild(groupBlock);

        // A group usually contains a vertical stack of items
        const innerStack = new VerticalStackBlock(`${groupId}_stack`);
        groupBlock.addChild(innerStack);

        // Register the new task ID to this inner stack
        let newTaskId = "";
        if (type === "workflow") {
            newTaskId = step.data.workflowExecutionStart?.executionId || "";
        } else if (type === "subflow") {
            newTaskId = step.delegationInfo?.[0]?.subTaskId || "";
        }

        // console.log(`[BlockBuilder] Group '${groupId}' registered for new task ID '${newTaskId}'`);

        if (newTaskId) {
            this.taskBlockMap.set(newTaskId, innerStack);
        }

        // Add the "Agent" node representing this group at the top of the stack
        if (type === "workflow") {
            // The Start node belongs to the workflow task ID
            // We pass connectToLast=false because we want to manually handle the connection to parent
            const startNodeId = this.addNode("genericAgentNode", step, "Start", { variant: "pill" }, newTaskId, false);
            
            // Explicitly set this as the last node for this task so subsequent nodes connect to it
            this.lastNodeByTaskId.set(newTaskId, startNodeId);

            // Connect to parent agent if available (using slot mechanism)
            const agentBlock = this.findActiveAgentNode(parentContainer);
            
            if (agentBlock && agentBlock.nodePayload) {
                 // Register slot on caller agent
                 const agentNode = agentBlock.nodePayload;
                 if (!agentNode.data.toolSlots) agentNode.data.toolSlots = [];

                 const slotIndex = (agentNode.data.toolSlots as any[]).length;
                 const toolPitch = NODE_HEIGHT + (VERTICAL_SPACING / 2);
                 const initialOffset = 25;
                 const yOffset = initialOffset + (slotIndex * toolPitch);

                 (agentNode.data.toolSlots as any[]).push({ id: startNodeId, yOffset });

                 const sourceHandle = `agent-out-${startNodeId}`;
                 const targetHandle = "peer-left-input";
                 this.createEdge(agentBlock.id, startNodeId, step.id, sourceHandle, targetHandle);
            } else {
                // Fallback if no parent agent found (e.g. root workflow or disconnected)
                // Connect from last node if any
                if (this.lastNodeId) {
                     // Use standard handles
                     let sourceHandle = "peer-bottom-output";
                     if (this.lastNodeBlock?.nodePayload?.type === "orchestratorNode") sourceHandle = "orch-bottom-output";
                     
                     this.createEdge(this.lastNodeId, startNodeId, step.id, sourceHandle, "peer-top-input");
                }
            }
        } else if (type === "subflow") {
            // For subflows, we want to connect to the caller agent with a slot
            // Note: addNode will handle the creation of InteractionRow and ToolsStack for this new agent
            const nodeId = this.addNode("genericAgentNode", step, label, {}, newTaskId, false);

            // Find the caller agent block to add a slot
            const agentBlock = this.findActiveAgentNode(parentContainer);

            if (agentBlock && agentBlock.nodePayload) {
                // Register slot on caller agent
                const agentNode = agentBlock.nodePayload;
                if (!agentNode.data.toolSlots) agentNode.data.toolSlots = [];

                const slotIndex = (agentNode.data.toolSlots as any[]).length;
                const toolPitch = NODE_HEIGHT + (VERTICAL_SPACING / 2);
                const initialOffset = 25;
                const yOffset = initialOffset + (slotIndex * toolPitch);

                (agentNode.data.toolSlots as any[]).push({ id: nodeId, yOffset });

                const sourceHandle = `agent-out-${nodeId}`;
                const targetHandle = "peer-left-input";
                this.createEdge(agentBlock.id, nodeId, step.id, sourceHandle, targetHandle);
            }
        }
    }

    private endGroup() {
        // No-op in stateless model
    }

    private handleToolInvocation(step: VisualizerStep) {
        const target = step.target || "";
        const toolName = step.data.toolInvocationStart?.toolName || target;

        // Skip workflow tool invocations as they are handled by WORKFLOW_EXECUTION_START
        if (target.includes("workflow_") || toolName.includes("workflow_")) {
            console.log(`[BlockBuilder] Skipping workflow tool invocation: ${target} / ${toolName}`);
            return;
        }

        const isPeer = step.data.toolInvocationStart?.isPeerInvocation || target.startsWith("peer_");

        if (isPeer) {
            const peerName = target.startsWith("peer_") ? target.substring(5) : target;
            const displayName = this.agentNameMap[peerName] || peerName;
            this.startGroup("subflow", step, displayName);
        } else {
            const taskId = step.owningTaskId;
            const container = this.getBlockForTask(taskId);
            const agentBlock = this.findActiveAgentNode(container);
            const sourceId = agentBlock ? agentBlock.id : undefined;

            this.addNode("genericToolNode", step, toolName, {}, taskId, true, sourceId, agentBlock || undefined);
        }
    }

    private handleToolResult(step: VisualizerStep) {
        const isPeer = step.data.toolResult?.isPeerResponse || (step.source && (step.source.startsWith("peer_") || step.source.startsWith("workflow_")));

        if (isPeer) {
            this.endGroup();
            this.handlePeerResponse(step);
        } else {
            // Local tool return - connect back to agent
            this.handleLLMResponse(step);
        }
    }

    private handlePeerResponse(step: VisualizerStep) {
        const taskId = step.owningTaskId;
        const container = this.getBlockForTask(taskId);
        const agentBlock = this.findActiveAgentNode(container);

        // Find the matching group block using functionCallId
        const targetFunctionCallId = step.data.toolResult?.functionCallId || step.functionCallId;
        let groupBlock = this.findGroupBlockByFunctionCallId(container, targetFunctionCallId);

        // Fallback to last group if specific match fails (legacy behavior)
        if (!groupBlock) {
            groupBlock = this.findLastSubflowGroup(container);
        }

        if (agentBlock && groupBlock) {
            let startNodeId: string | undefined;
            let finishNodeId: string | undefined;

            // Find Start Node (first node in group)
            if (groupBlock.children.length > 0 && groupBlock.children[0] instanceof VerticalStackBlock) {
                const stack = groupBlock.children[0];
                if (stack.children.length > 0) {
                    const firstChild = stack.children[0];
                    if (firstChild instanceof HorizontalStackBlock) {
                        // New structure with Interaction Row
                        if (firstChild.children.length > 0 && firstChild.children[0] instanceof LeafBlock) {
                            startNodeId = firstChild.children[0].id;
                        }
                    } else if (firstChild instanceof LeafBlock) {
                        // Old/Fallback structure
                        startNodeId = firstChild.id;
                    }
                }
            }

            // Find Finish Node
            finishNodeId = this.findNodeIdByLabel(groupBlock, "Finish");

            // Fallback: use the last node in the group (likely the Finish node if label lookup failed)
            if (!finishNodeId) {
                finishNodeId = this.findLastNodeInGroup(groupBlock);
                // If the last node is the start node, it means no progress was made or finish node wasn't added.
                // In that case, we don't want to treat it as a distinct finish node.
                if (finishNodeId === startNodeId) {
                    finishNodeId = undefined;
                }
            }

            const sourceNodeId = finishNodeId || startNodeId;

            if (sourceNodeId && startNodeId) {
                const sourceHandle = "peer-left-output";
                
                // Check if the agent block has a slot for the START node (which represents the subflow/workflow)
                let targetHandle = `agent-in-${startNodeId}`;
                const agentNodeData = agentBlock.nodePayload?.data;
                const hasSlot = Array.isArray(agentNodeData?.toolSlots) && agentNodeData.toolSlots.some((slot: any) => slot.id === startNodeId);
                
                if (!hasSlot) {
                    // Fallback to standard input handle if no slot exists (e.g. for workflows where tool invocation was skipped)
                    if (agentBlock.nodePayload?.type === "orchestratorNode") {
                        targetHandle = "orch-left-input";
                    } else {
                        targetHandle = "peer-left-input";
                    }
                }

                this.createEdge(sourceNodeId, agentBlock.id, step.id, sourceHandle, targetHandle);

                // Reset lastNodeId to the Agent
                this.lastNodeId = agentBlock.id;
                this.lastNodeBlock = agentBlock;
                if (taskId) {
                    this.lastNodeByTaskId.set(taskId, agentBlock.id);
                }
            } else {
                console.log(`[BlockBuilder] handlePeerResponse: Could not find source/start nodes in group ${groupBlock.id}. Start: ${startNodeId}, Finish: ${finishNodeId}`);
            }
        }
    }

    private findNodeIdByLabel(block: LayoutBlock, label: string): string | undefined {
        if (block instanceof LeafBlock && block.nodePayload?.data?.label === label) {
            return block.id;
        }
        for (const child of block.children) {
            const found = this.findNodeIdByLabel(child, label);
            if (found) return found;
        }
        return undefined;
    }

    private findLastNodeInGroup(groupBlock: LayoutBlock): string | undefined {
        if (groupBlock.children.length > 0 && groupBlock.children[0] instanceof VerticalStackBlock) {
            const stack = groupBlock.children[0];
            if (stack.children.length > 0) {
                const lastChild = stack.children[stack.children.length - 1];
                // Check if it's a row (Agent)
                if (lastChild instanceof HorizontalStackBlock && lastChild.children.length > 0) {
                    const firstLeaf = lastChild.children[0];
                    if (firstLeaf instanceof LeafBlock) {
                        return firstLeaf.id;
                    }
                } 
                // Check if it's a leaf (Tool/Node)
                else if (lastChild instanceof LeafBlock) {
                    return lastChild.id;
                }
            }
        }
        return undefined;
    }

    private findGroupBlockByFunctionCallId(container: LayoutBlock, functionCallId?: string): LayoutBlock | null {
        if (!functionCallId) return null;
        
        // Search backwards as recent groups are more likely
        for (let i = container.children.length - 1; i >= 0; i--) {
            const block = container.children[i];
            if (block instanceof GroupBlock) {
                if (block.nodePayload?.data?.functionCallId === functionCallId) {
                    return block;
                }
            }
        }
        return null;
    }

    private findLastSubflowGroup(container: LayoutBlock): LayoutBlock | null {
        for (let i = container.children.length - 1; i >= 0; i--) {
            const block = container.children[i];
            if (block instanceof GroupBlock) {
                return block;
            }
        }
        return null;
    }

    private handleWorkflowNodeStart(step: VisualizerStep) {
        const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
        const nodeId = step.data.workflowNodeExecutionStart?.nodeId || "unknown";
        const label = step.data.workflowNodeExecutionStart?.agentName || nodeId;
        const taskId = step.owningTaskId; // This is the Workflow Execution ID
        const container = this.getBlockForTask(taskId);
        const parentNodeId = step.data.workflowNodeExecutionStart?.parentNodeId;

        let targetContainer = container;
        let explicitSourceId: string | undefined;

        // If we are currently in a HorizontalStack (Map/Fork container),
        // any new node execution implies a new vertical branch/iteration.
        if (container instanceof HorizontalStackBlock) {
            const vStack = new VerticalStackBlock(`vstack_${nodeId}`);
            container.addChild(vStack);
            targetContainer = vStack;

            // If this is a child of a Map/Fork, we want to connect from the Map/Fork node
            if (parentNodeId) {
                // Scope by taskId to ensure we get the parent node from the correct workflow execution
                explicitSourceId = this.yamlNodeIdToGeneratedId.get(`${taskId}:${parentNodeId}`);
            }
        }

        if (nodeType === "map" || nodeType === "fork") {
            // Start a horizontal block for parallel execution
            // First add the control node itself (e.g. "Map" or "Fork" pill)
            const mapNodeId = this.addNode("genericAgentNode", step, label, { variant: "pill" }, taskId, true, explicitSourceId, undefined, targetContainer);
            // Scope by taskId
            this.yamlNodeIdToGeneratedId.set(`${taskId}:${nodeId}`, mapNodeId);

            const hStack = new HorizontalStackBlock(`hstack_${nodeId}`);
            hStack.anchorNodeId = mapNodeId; // Set anchor for children branches
            targetContainer.addChild(hStack);

            // We need to map `taskId` to `hStack` so subsequent children are added to it
            this.taskBlockMap.set(taskId, hStack);
        } else {
            // Regular node
            let variant = "default";
            if (nodeType === "conditional") variant = "pill";
            if (nodeType === "map" || nodeType === "fork") variant = "pill";

            let nodeTypeStr = "genericAgentNode";
            if (nodeType === "conditional") nodeTypeStr = "conditionalNode";

            // Add the node to the workflow container
            const newNodeId = this.addNode(nodeTypeStr, step, label, { variant }, taskId, true, explicitSourceId, undefined, targetContainer);
            // Scope by taskId
            this.yamlNodeIdToGeneratedId.set(`${taskId}:${nodeId}`, newNodeId);

            // If this node is an Agent, it will have its own sub-task ID for execution.
            // We need to register the ToolsStack of this new node to that sub-task ID
            // so that LLM calls inside it are placed correctly.
            const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
            if (subTaskId && nodeType === "agent") {
                // addNode creates a HorizontalStack (Row) -> VerticalStack (Tools) for agents.
                // We need to find that ToolsStack and map it to subTaskId.
                
                // The targetContainer (innerStack of Group or vStack of iteration) has children. 
                // The last child is the Row we just added.
                const lastChild = targetContainer.children[targetContainer.children.length - 1];
                if (lastChild instanceof HorizontalStackBlock) {
                    // The second child of the Row is the ToolsStack
                    if (lastChild.children.length > 1 && lastChild.children[1] instanceof VerticalStackBlock) {
                        const toolsStack = lastChild.children[1];
                        this.taskToolStackMap.set(subTaskId, toolsStack);
                        // Also map the main block map for good measure, though tools usually look up tool stack
                        this.taskBlockMap.set(subTaskId, toolsStack);
                    }
                }
            }
        }
    }

    private handleWorkflowNodeResult(step: VisualizerStep) {
        const nodeId = step.data.workflowNodeExecutionResult?.nodeId;
        const taskId = step.owningTaskId;
        const container = this.getBlockForTask(taskId);

        // Check if we need to pop a VerticalStack (end of branch/iteration)
        if (container.id === `vstack_${nodeId}`) {
            // We need to "pop" by resetting the map to the parent of this vStack.
            if (container.parent) {
                this.taskBlockMap.set(taskId, container.parent);
            }
        }

        // Check if we need to pop a HorizontalStack (end of Map/Fork)
        // We re-fetch container because we might have just popped
        const currentContainer = this.getBlockForTask(taskId);
        if (currentContainer.id === `hstack_${nodeId}`) {
            if (currentContainer.parent) {
                this.taskBlockMap.set(taskId, currentContainer.parent);
            }

            // Add a "Join" node after the parallel block
            // We don't connect to last because we want to connect from all branches
            const joinNodeId = this.addNode("genericAgentNode", step, "Join", { variant: "pill" }, taskId, false);
            
            // Connect all branches to the Join node
            if (currentContainer instanceof HorizontalStackBlock) {
                for (const branchStack of currentContainer.children) {
                    const lastLeaf = this.findLastLeaf(branchStack);
                    if (lastLeaf) {
                        // Determine source handle
                        let sourceHandle = "peer-bottom-output";
                        if (lastLeaf.nodePayload?.type === "genericToolNode") {
                            sourceHandle = `${lastLeaf.id}-tool-bottom-output`;
                        } else if (lastLeaf.nodePayload?.type === "llmNode") {
                            sourceHandle = "llm-bottom-output";
                        }
                        
                        this.createEdge(lastLeaf.id, joinNodeId, step.id, sourceHandle, "peer-top-input");
                    }
                }
            }
            
            // Update lastNodeId to Join node so subsequent nodes connect to it
            this.lastNodeId = joinNodeId;
            this.lastNodeByTaskId.set(taskId, joinNodeId);
        }
    }

    private findLastLeaf(block: LayoutBlock): LeafBlock | null {
        if (block instanceof LeafBlock) {
            return block;
        }
        if (block.children.length > 0) {
            // Search backwards
            for (let i = block.children.length - 1; i >= 0; i--) {
                const leaf = this.findLastLeaf(block.children[i]);
                if (leaf) return leaf;
            }
        }
        return null;
    }

    private handleWorkflowExecutionResult(step: VisualizerStep) {
        const taskId = step.owningTaskId;
        // Add Finish node
        const finishNodeId = this.addNode("genericAgentNode", step, "Finish", { variant: "pill" }, taskId);

        // Fix up return edge if it was already created from Start Node (due to event ordering)
        const innerStack = this.taskBlockMap.get(taskId);
        if (innerStack && innerStack.parent instanceof GroupBlock) {
            const groupBlock = innerStack.parent;
            const startNodeId = this.findNodeIdByLabel(groupBlock, "Start");

            if (startNodeId) {
                // Find edge from Start Node that targets an agent input slot
                const edge = this.edges.find(e => e.source === startNodeId && e.targetHandle?.startsWith("agent-in-"));
                if (edge) {
                    console.log(`[BlockBuilder] Redirecting return edge ${edge.id} from ${startNodeId} to ${finishNodeId}`);
                    edge.source = finishNodeId;
                    // Update edge ID to maintain consistency
                    edge.id = `e_${finishNodeId}_${edge.target}`;
                }
            }
        }
    }

    private handleTaskCompleted(step: VisualizerStep) {
        const taskId = step.owningTaskId;
        const taskBlock = this.taskBlockMap.get(taskId);

        // Check if this is a sub-task completion (taskBlock is innerStack of a Group)
        if (taskBlock && taskBlock instanceof VerticalStackBlock) {
            const groupBlock = taskBlock.parent;
            if (groupBlock instanceof GroupBlock) {
                // This is a subflow group
                // Find the parent agent
                // groupBlock.parent is the ToolStack of the parent
                const toolStack = groupBlock.parent;
                if (toolStack && toolStack.parent instanceof HorizontalStackBlock) {
                    const row = toolStack.parent;
                    if (row.children.length > 0 && row.children[0] instanceof LeafBlock) {
                        const parentAgent = row.children[0];

                        // Find the sub-agent node in the group to connect from
                        // taskBlock (innerStack) -> Row -> Agent
                        let subAgentId: string | undefined;

                        // Prefer Finish node if available
                        subAgentId = this.findNodeIdByLabel(groupBlock, "Finish");

                        if (!subAgentId) {
                            // Fallback to first child (Start node)
                            if (taskBlock.children.length > 0) {
                                const firstChild = taskBlock.children[0];
                                if (firstChild instanceof HorizontalStackBlock && firstChild.children.length > 0) {
                                    subAgentId = firstChild.children[0].id;
                                } else if (firstChild instanceof LeafBlock) {
                                    subAgentId = firstChild.id;
                                }
                            }
                        }

                        // We need the Start node ID to determine the target handle (slot)
                        let startNodeId = this.findNodeIdByLabel(groupBlock, "Start");
                        if (!startNodeId && subAgentId) {
                            // If we can't find Start node by label, assume subAgentId is the start node if we fell back
                            // But if subAgentId is Finish, we still need Start ID for the slot.
                            // Let's try to find the first node again.
                            if (taskBlock.children.length > 0) {
                                const firstChild = taskBlock.children[0];
                                if (firstChild instanceof HorizontalStackBlock && firstChild.children.length > 0) {
                                    startNodeId = firstChild.children[0].id;
                                } else if (firstChild instanceof LeafBlock) {
                                    startNodeId = firstChild.id;
                                }
                            }
                        }

                        if (subAgentId && parentAgent && startNodeId) {
                            const sourceHandle = "peer-left-output";
                            const targetHandle = `agent-in-${startNodeId}`;
                            this.createEdge(subAgentId, parentAgent.id, step.id, sourceHandle, targetHandle);
                        }
                    }
                }
            }
        }
    }

    public printTree(): void {
        console.groupCollapsed("[BlockBuilder] Layout Tree Structure");
        this.printBlockRecursive(this.root, 0);
        console.groupEnd();
    }

    private printBlockRecursive(block: LayoutBlock, depth: number) {
        const indent = "  ".repeat(depth);
        const type = block.constructor.name;
        const id = block.id;
        const label = block.nodePayload?.data?.label || "N/A";
        const nodeType = block.nodePayload?.type || "N/A";
        const dims = `${block.width}x${block.height}`;
        const pos = `(${block.x},${block.y})`;
        
        console.log(`${indent}└─ [${type}] ${id} ${dims} ${pos} (Node: ${nodeType} "${label}")`);
        
        for (const child of block.children) {
            this.printBlockRecursive(child, depth + 1);
        }
    }
}
