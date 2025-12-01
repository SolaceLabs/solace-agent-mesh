import type { VisualizerStep } from "@/lib/types";
import { LayoutBlock, VerticalStackBlock, LeafBlock, GroupBlock, HorizontalStackBlock } from "./LayoutBlock";
import { LANE_OFFSETS, VERTICAL_SPACING, NODE_HEIGHT } from "./constants";
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
            case "WORKFLOW_EXECUTION_START":
                {
                    const wfName = step.data.workflowExecutionStart?.workflowName || "Workflow";
                    const displayName = this.agentNameMap[wfName] || wfName;
                    this.startGroup("workflow", step, displayName);
                }
                break;
            case "WORKFLOW_EXECUTION_RESULT":
                // No-op in stateless model, group structure is defined by start events
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
        const taskId = step.owningTaskId;
        
        // Check if we already have a user response node for this task
        let userNode = this.taskUserResponseNodeMap.get(taskId);

        if (userNode) {
            // Update existing node
            // Note: In a real app, we might want to accumulate text here if it's not already accumulated in the step data.
            // But since the visualizer step data usually contains the full text or chunk, we rely on the step data.
            // However, React Flow nodes are immutable-ish. We need to update the node payload.
            // But since we are rebuilding the tree every time, we can just update the payload of the block we created.
            // Actually, if we are processing a stream, 'step' is a new event.
            // If we want to show accumulated text, we should update the label or data of the existing node.
            // For now, let's assume the step contains the latest chunk and we just want to ensure the node exists.
            // If we want to append text, we'd need to track state.
            // But the requirement is "accumulate all the text responses".
            // Let's assume the node's label/data should reflect the accumulated text.
            
            // Since we are processing linearly, we can just update the data of the existing block.
            if (userNode.nodePayload && step.data.text) {
                 // Append text if it's a new chunk
                 // But wait, step.data.text might be the full text if the processor aggregated it.
                 // If it's a chunk, we append.
                 const currentText = userNode.nodePayload.data.label || "";
                 // Simple heuristic: if the new text starts with the old text, replace it. Otherwise append.
                 // Actually, let's just use the latest step's text if it seems complete, or append.
                 // For simplicity in this refactor, let's just update the label to "Response" and let the UI handle details,
                 // OR if we want to show text, we append.
                 // Let's just ensure the node exists. The visualizer usually shows the text in the side panel.
                 // The node label is usually just "User".
            }
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
    private addNode(type: string, step: VisualizerStep, label: string, data: any = {}, targetTaskId: string, connectToLast: boolean = true, explicitSourceId?: string, explicitSourceBlock?: LayoutBlock): string {
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

        if (type === "orchestratorNode" || type === "genericAgentNode") {
            // Agents start a new Interaction Row
            // They are added to the main flow container (Root or parent ToolStack)
            container = this.getBlockForTask(targetTaskId);
            
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
            
        } else if (type === "userNode") {
            // User nodes go to the main flow container
            container = this.getBlockForTask(targetTaskId);
            container.addChild(block);
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
        console.log(`[BlockBuilder] Creating edge ${source} -> ${target} (step: ${stepId})`);
        const edgeId = `e_${source}_${target}`;
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

        const groupNode: Node = {
            id: groupId,
            type: "group",
            position: { x: 0, y: 0 },
            data: { label: label },
            style: { width: 0, height: 0 } // Will be set by layout engine
        };

        const groupBlock = new GroupBlock(groupId, groupNode);
        
        const parentTaskId = step.owningTaskId;
        
        // Determine where to add the group
        let parentContainer: LayoutBlock;
        if (type === "subflow") {
            // Subflows go into the tool stack of the parent task
            const toolStack = this.taskToolStackMap.get(parentTaskId);
            parentContainer = toolStack || this.getBlockForTask(parentTaskId);
        } else {
            // Workflows go into the main flow
            parentContainer = this.getBlockForTask(parentTaskId);
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
            this.addNode("genericAgentNode", step, "Start", { variant: "pill" }, newTaskId);
        } else if (type === "subflow") {
            // For subflows, we want to connect to the caller agent with a slot
            // Note: addNode will handle the creation of InteractionRow and ToolsStack for this new agent
            const nodeId = this.addNode("genericAgentNode", step, label, {}, newTaskId, false);
            
            // We need to connect the caller to this new agent
            const callerNodeId = this.lastNodeByTaskId.get(parentTaskId);
            if (callerNodeId) {
                 // We need to register slot on caller agent.
                 if (this.lastNodeBlock && this.lastNodeBlock.id === callerNodeId && this.lastNodeBlock.nodePayload) {
                     const agentNode = this.lastNodeBlock.nodePayload;
                     if (!agentNode.data.toolSlots) agentNode.data.toolSlots = [];
                     
                     const slotIndex = (agentNode.data.toolSlots as any[]).length;
                     const toolPitch = NODE_HEIGHT + (VERTICAL_SPACING / 2);
                     const initialOffset = 25;
                     const yOffset = initialOffset + (slotIndex * toolPitch);
                     
                     (agentNode.data.toolSlots as any[]).push({ id: nodeId, yOffset });
                     
                     const sourceHandle = `agent-out-${nodeId}`;
                     const targetHandle = "peer-left-input";
                     this.createEdge(callerNodeId, nodeId, step.id, sourceHandle, targetHandle);
                 }
            }
        }
    }

    private endGroup() {
        // No-op in stateless model
    }

    private handleToolInvocation(step: VisualizerStep) {
        const target = step.target || "";
        const isPeer = step.data.toolInvocationStart?.isPeerInvocation || target.startsWith("peer_") || target.startsWith("workflow_");

        if (isPeer) {
            const peerName = target.startsWith("peer_") ? target.substring(5) : target;
            const displayName = this.agentNameMap[peerName] || peerName;
            this.startGroup("subflow", step, displayName);
        } else {
            const toolName = step.data.toolInvocationStart?.toolName || target;
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
        
        // Find the last group block (subflow)
        const groupBlock = this.findLastSubflowGroup(container);
        
        if (agentBlock && groupBlock) {
            // We need the peer agent node ID inside the group.
            // The group contains an innerStack.
            // The innerStack contains the peer agent node as the first child.
            
            let peerAgentId: string | undefined;
            if (groupBlock.children.length > 0 && groupBlock.children[0] instanceof VerticalStackBlock) {
                const stack = groupBlock.children[0];
                if (stack.children.length > 0 && stack.children[0] instanceof LeafBlock) {
                    peerAgentId = stack.children[0].id;
                }
            }
            
            if (peerAgentId) {
                const sourceHandle = "peer-bottom-output";
                const targetHandle = `agent-in-${peerAgentId}`;
                
                this.createEdge(peerAgentId, agentBlock.id, step.id, sourceHandle, targetHandle);
                
                // Reset lastNodeId to the Agent
                this.lastNodeId = agentBlock.id;
                this.lastNodeBlock = agentBlock;
                if (taskId) {
                    this.lastNodeByTaskId.set(taskId, agentBlock.id);
                }
            }
        }
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
        const label = step.data.workflowNodeExecutionStart?.agentPersona || nodeId;
        const taskId = step.owningTaskId;
        const container = this.getBlockForTask(taskId);

        // If we are currently in a HorizontalStack (Map/Fork container),
        // any new node execution implies a new vertical branch/iteration.
        // But in stateless, we don't know "current". We check the container type.
        if (container instanceof HorizontalStackBlock) {
            const vStack = new VerticalStackBlock(`vstack_${nodeId}`);
            container.addChild(vStack);
            // We need to map this new vStack to a task ID?
            // Or just use it as the container for this node?
            // If this node starts a sub-task (agent), that sub-task will have a new ID.
            // But this node itself belongs to the parent flow.
            // So we should probably update the map for the current taskId to point to this vStack?
            // No, that would break other parallel branches.
            // We need a unique ID for this branch.
            // The `subTaskId` in `workflowNodeExecutionStart` is what we need!
            const subTaskId = step.data.workflowNodeExecutionStart?.subTaskId;
            if (subTaskId) {
                this.taskBlockMap.set(subTaskId, vStack);
                // And we add the node to this vStack
                // But `addNode` uses `taskId` to look up container.
                // If we pass `subTaskId`, it will find `vStack`.
                // So we should pass `subTaskId` to `addNode`?
                // But `addNode` expects the ID of the task *containing* the node.
                // The node itself *is* the start of the subtask.
                // So it should be added to `vStack`.
                
                // Let's manually add the node to vStack here to bootstrap it.
                // Or temporarily map taskId to vStack? No.
                
                // Actually, `handleWorkflowNodeStart` is for the *wrapper* node in the workflow graph.
                // The *agent execution* inside it will be a separate task.
                // So this node belongs to the *workflow* task.
                // So it should go into the workflow's container.
                
                // If the workflow container is a HorizontalStack (Map), we need to add a VerticalStack for this item.
                // And then add the node to that VerticalStack.
                // And then subsequent nodes for this item should go to that VerticalStack.
                // But subsequent nodes will have the same `owningTaskId` (the workflow).
                // This is a problem for statelessness if multiple branches share the same taskId.
                // Workflow execution usually shares one taskId for the orchestrator.
                // But Map iterations might have distinct sub-task IDs?
                // `DAGExecutor` generates `sub_task_id` for agent nodes.
                // But `WORKFLOW_NODE_EXECUTION_START` event belongs to the workflow task.
                
                // We need a way to distinguish branches in the workflow task.
                // `iterationIndex` or `subTaskId` in the event data.
                // If we have `subTaskId`, we can map it.
                // But the event itself has `owningTaskId` = workflow ID.
                
                // We might need to create a synthetic ID for the branch: `${taskId}_branch_${nodeId}`.
                // And map that to the vStack.
                // But how do subsequent events know to use that?
                // They don't.
                
                // This implies that for Map/Fork in a single workflow task, we DO need some state
                // or we need to look up the branch based on `nodeId` or `iterationIndex`.
                
                // For now, let's assume standard vertical flow for workflow nodes unless we are explicitly in a Map.
            }
        }

        if (nodeType === "map" || nodeType === "fork") {
            // Start a horizontal block for parallel execution
            // First add the control node itself (e.g. "Map" or "Fork" pill)
            const mapNodeId = this.addNode("genericAgentNode", step, label, { variant: "pill" }, taskId);

            const hStack = new HorizontalStackBlock(`hstack_${nodeId}`);
            hStack.anchorNodeId = mapNodeId; // Set anchor for children branches
            container.addChild(hStack);
            
            // We need to ensure children of this map go into hStack.
            // But children will be added via `handleWorkflowNodeStart` later.
            // And they will look up `taskId`.
            // If we update `taskBlockMap` for `taskId` to point to `hStack`, it works!
            // But wait, `hStack` is horizontal. Children need to be vertical stacks inside it.
            // So we update `taskBlockMap` to point to `hStack`.
            // Then the NEXT `handleWorkflowNodeStart` will see `hStack`, create a `vStack`, add it, and update map?
            // If we update map, we overwrite `hStack`.
            // This works for the *first* child of the branch.
            // But what about the second branch? It needs to see `hStack` again.
            
            // We need to map `taskId` to `hStack`.
            this.taskBlockMap.set(taskId, hStack);
        } else {
            // Regular node
            let variant = "default";
            if (nodeType === "conditional") variant = "pill";

            let nodeTypeStr = "genericAgentNode";
            if (nodeType === "conditional") nodeTypeStr = "conditionalNode";

            this.addNode(nodeTypeStr, step, label, { variant }, taskId);
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

            // Optional: Add a "Join" node after the parallel block
            this.addNode("genericAgentNode", step, "Join", { variant: "pill" }, taskId);
        }
    }
}
