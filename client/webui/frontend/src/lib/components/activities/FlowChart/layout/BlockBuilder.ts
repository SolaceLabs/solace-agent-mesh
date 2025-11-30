import type { VisualizerStep } from "@/lib/types";
import { LayoutBlock, VerticalStackBlock, LeafBlock, GroupBlock, HorizontalStackBlock } from "./LayoutBlock";
import { LANE_OFFSETS } from "./constants";
import type { Node, Edge } from "@xyflow/react";

/**
 * Responsible for converting a linear stream of VisualizerSteps into a hierarchical LayoutBlock tree.
 */
export class BlockBuilder {
    private root: VerticalStackBlock;
    private stack: LayoutBlock[];
    private nodeCounter: number = 0;
    private groupCounter: number = 0;
    
    private edges: Edge[] = [];
    private lastNodeId: string | null = null;
    private lastNodeBlock: LayoutBlock | null = null;
    private lastNodeByTaskId: Map<string, string> = new Map();
    private agentNameMap: Record<string, string>;

    constructor(agentNameMap: Record<string, string> = {}) {
        this.root = new VerticalStackBlock("root");
        this.stack = [this.root];
        this.agentNameMap = agentNameMap;
    }

    public build(steps: VisualizerStep[]): { root: LayoutBlock, edges: Edge[] } {
        for (const step of steps) {
            this.processStep(step);
        }
        return { root: this.root, edges: this.edges };
    }

    private get currentBlock(): LayoutBlock {
        return this.stack[this.stack.length - 1];
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
                this.endGroup();
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
        this.addNode("userNode", step, "User", { isTopNode: true });

        // 2. Add Orchestrator Node immediately
        const agentName = step.target || "Orchestrator";
        const displayName = this.agentNameMap[agentName] || agentName;
        this.addNode("orchestratorNode", step, displayName);
    }

    private handleLLMCall(step: VisualizerStep) {
        this.addNode("llmNode", step, "LLM");
    }

    private handleLLMResponse(step: VisualizerStep) {
        // Find the active agent node (Orchestrator or Peer)
        const agentBlock = this.findActiveAgentNode();
        
        // Find the last tool/LLM node to connect back from
        // We can't rely on lastNodeId because interleaved events (like progress updates) might have changed it
        const toolBlock = this.findLastToolOrLLMNode();
        
        if (agentBlock && toolBlock) {
            const toolId = toolBlock.id;
            
            // Create return edge from Tool/LLM back to Agent
            // We use the dynamic handle corresponding to the tool slot
            const targetHandle = `agent-in-${toolId}`;
            
            // Determine source handle based on tool type (heuristic based on ID prefix)
            let sourceHandle = "peer-bottom-output";
            if (toolId.startsWith("llmNode")) {
                sourceHandle = "llm-bottom-output";
            } else if (toolId.startsWith("genericToolNode")) {
                sourceHandle = `${toolId}-tool-bottom-output`;
            }

            this.createEdge(toolId, agentBlock.id, step.id, sourceHandle, targetHandle);

            // Reset lastNodeId to the Agent, so subsequent steps (like response text) connect from the Agent
            this.lastNodeId = agentBlock.id;
            this.lastNodeBlock = agentBlock;

            // Update task tracking so next node connects to Agent
            if (step.owningTaskId) {
                this.lastNodeByTaskId.set(step.owningTaskId, agentBlock.id);
            }
        }
    }

    private findLastToolOrLLMNode(): LayoutBlock | null {
        // Search backwards in the current block for the last tool or LLM node
        for (let i = this.currentBlock.children.length - 1; i >= 0; i--) {
            const block = this.currentBlock.children[i];
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
        // Only add user node for root level responses (Orchestrator -> User)
        if (this.stack.length === 1 && !step.isSubTaskStep) {
            // Ensure we connect from the Orchestrator, not from a random tool/LLM that might have just finished
            const agentBlock = this.findActiveAgentNode();
            const explicitSourceId = agentBlock ? agentBlock.id : undefined;
            
            this.addNode("userNode", step, "User", { isBottomNode: true }, true, explicitSourceId);
        }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private addNode(type: string, step: VisualizerStep, label: string, data: any = {}, connectToLast: boolean = true, explicitSourceId?: string): string {
        const nodeId = `${type}_${this.nodeCounter++}`;
        const node: Node = {
            id: nodeId,
            type: type,
            position: { x: 0, y: 0 }, // Will be set by layout engine
            data: { label: label, visualizerStepId: step.id, ...data }
        };
        const block = new LeafBlock(nodeId, node);
        
        // Assign lane offset based on node type
        if (type === "userNode") {
            block.laneOffset = LANE_OFFSETS.USER;
        } else if (type === "genericToolNode" || type === "llmNode") {
            block.laneOffset = LANE_OFFSETS.TOOL;
        } else {
            block.laneOffset = LANE_OFFSETS.MAIN;
        }

        this.currentBlock.addChild(block);
        
        // Determine source node for edge
        let sourceNodeId = explicitSourceId || this.lastNodeId;
        let sourceType = "";
        let sourceBlock = this.lastNodeBlock;

        // Check if we are the first node in the current block and if the block has an anchor
        // This handles connecting parallel branches to their parent Map/Fork node
        if (!explicitSourceId && this.currentBlock.children.length === 1 && this.currentBlock.parent?.anchorNodeId) {
             sourceNodeId = this.currentBlock.parent.anchorNodeId;
             sourceType = "genericAgentNode"; 
             // Note: We don't have easy access to the anchor block object here, but that's okay for now
        }
        // Otherwise, check task-specific history for sequential flow
        else if (!explicitSourceId && step.owningTaskId && this.lastNodeByTaskId.has(step.owningTaskId)) {
            sourceNodeId = this.lastNodeByTaskId.get(step.owningTaskId)!;
            sourceType = sourceNodeId.split("_")[0];
            // Note: lastNodeBlock might not match sourceNodeId if we jumped tasks, but we use it for Agent->Tool check below
        } else if (sourceNodeId) {
            sourceType = sourceNodeId.split("_")[0];
        }

        // Special handling for Agent -> Tool/LLM connections to use dynamic slots
        let customSourceHandle: string | undefined;
        let customTargetHandle: string | undefined;

        if (connectToLast && sourceNodeId && (type === "llmNode" || type === "genericToolNode")) {
            // If source is an agent, add a tool slot
            if (sourceType === "orchestratorNode" || sourceType === "genericAgentNode") {
                // We need to update the agent node data. 
                // If sourceBlock is available and matches sourceNodeId, use it.
                // Otherwise we might miss adding the slot if we switched tasks.
                // For now, assume sequential flow for LLM calls (usually true).
                // If explicitSourceId was used, we might need to find the block if sourceBlock is stale.
                if (explicitSourceId && (!sourceBlock || sourceBlock.id !== explicitSourceId)) {
                    // Try to find the block in current children (common case)
                    sourceBlock = this.currentBlock.children.find(b => b.id === explicitSourceId) || null;
                }

                if (sourceBlock && sourceBlock.id === sourceNodeId && sourceBlock.nodePayload) {
                    const agentNode = sourceBlock.nodePayload;
                    if (!agentNode.data.toolSlots) agentNode.data.toolSlots = [];
                    
                    // Calculate Y offset for the slot
                    // We estimate based on existing slots to stack them
                    const slotIndex = (agentNode.data.toolSlots as any[]).length;
                    const yOffset = 40 + (slotIndex * 20); // Start at 40px down
                    
                    (agentNode.data.toolSlots as any[]).push({ id: nodeId, yOffset });

                    // Update agent node height to accommodate slots
                    // This ensures measure() picks up the correct height for layout calculations
                    const requiredHeight = Math.max(50, yOffset + 30); // 50 is default NODE_HEIGHT, +30 for padding
                    agentNode.style = { ...agentNode.style, height: `${requiredHeight}px` };
                    
                    customSourceHandle = `agent-out-${nodeId}`;
                    customTargetHandle = type === "llmNode" ? "llm-left-input" : `${nodeId}-tool-left-input`;

                    // If this is the FIRST tool call for this agent block, pull it up
                    // We check if the previous sibling in the current container is the source agent
                    // Since we already added 'block' to children, we look at index - 2
                    if (this.currentBlock.children.length > 1) {
                        const prevSibling = this.currentBlock.children[this.currentBlock.children.length - 2];
                        if (prevSibling.id === sourceNodeId) {
                            block.pullUp = true;
                            console.log(`[BlockBuilder] Setting pullUp=true for ${block.id} (sibling of ${prevSibling.id})`);
                        }
                    }
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
        if (step.owningTaskId) {
            this.lastNodeByTaskId.set(step.owningTaskId, nodeId);
        }
        
        return nodeId;
    }

    private findActiveAgentNode(): LayoutBlock | null {
        // Search backwards in the current block for the last agent node
        for (let i = this.currentBlock.children.length - 1; i >= 0; i--) {
            const block = this.currentBlock.children[i];
            if (block.nodePayload) {
                const type = block.nodePayload.type;
                if (type === "orchestratorNode" || type === "genericAgentNode") {
                    return block;
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
        const groupNode: Node = {
            id: groupId,
            type: "group",
            position: { x: 0, y: 0 },
            data: { label: label },
            style: { width: 0, height: 0 } // Will be set by layout engine
        };

        const groupBlock = new GroupBlock(groupId, groupNode);
        groupBlock.laneOffset = LANE_OFFSETS.MAIN; // Groups align with Main flow
        
        this.currentBlock.addChild(groupBlock);

        // A group usually contains a vertical stack of items
        const innerStack = new VerticalStackBlock(`${groupId}_stack`);
        groupBlock.addChild(innerStack);

        // Push the inner stack so subsequent nodes are added to it
        this.stack.push(innerStack);

        // Add the "Agent" node representing this group at the top of the stack
        // For workflows, it's a "Start" node. For peers, it's the Peer Agent node.
        if (type === "workflow") {
            this.addNode("genericAgentNode", step, "Start", { variant: "pill" });
        } else if (type === "subflow") {
            this.addNode("genericAgentNode", step, label);
        }
    }

    private endGroup() {
        // Ensure we don't pop the root
        if (this.stack.length > 1) {
            this.stack.pop();
        }
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
            this.addNode("genericToolNode", step, toolName);
        }
    }

    private handleToolResult(step: VisualizerStep) {
        const isPeer = step.data.toolResult?.isPeerResponse || (step.source && (step.source.startsWith("peer_") || step.source.startsWith("workflow_")));

        if (isPeer) {
            this.endGroup();
        } else {
            // Local tool return - connect back to agent
            this.handleLLMResponse(step);
        }
    }

    private handleWorkflowNodeStart(step: VisualizerStep) {
        const nodeType = step.data.workflowNodeExecutionStart?.nodeType;
        const nodeId = step.data.workflowNodeExecutionStart?.nodeId || "unknown";
        const label = step.data.workflowNodeExecutionStart?.agentPersona || nodeId;

        // If we are currently in a HorizontalStack (Map/Fork container),
        // any new node execution implies a new vertical branch/iteration.
        if (this.currentBlock instanceof HorizontalStackBlock) {
            const vStack = new VerticalStackBlock(`vstack_${nodeId}`);
            this.currentBlock.addChild(vStack);
            this.stack.push(vStack);
        }

        if (nodeType === "map" || nodeType === "fork") {
            // Start a horizontal block for parallel execution
            // First add the control node itself (e.g. "Map" or "Fork" pill)
            const mapNodeId = this.addNode("genericAgentNode", step, label, { variant: "pill" });

            const hStack = new HorizontalStackBlock(`hstack_${nodeId}`);
            hStack.anchorNodeId = mapNodeId; // Set anchor for children branches
            this.currentBlock.addChild(hStack);
            this.stack.push(hStack);
        } else {
            // Regular node
            let variant = "default";
            if (nodeType === "conditional") variant = "pill";

            let nodeTypeStr = "genericAgentNode";
            if (nodeType === "conditional") nodeTypeStr = "conditionalNode";

            this.addNode(nodeTypeStr, step, label, { variant });
        }
    }

    private handleWorkflowNodeResult(step: VisualizerStep) {
        const nodeId = step.data.workflowNodeExecutionResult?.nodeId;

        // Check if we need to pop a VerticalStack (end of branch/iteration)
        if (this.currentBlock.id === `vstack_${nodeId}`) {
            this.stack.pop();
        }

        // Check if we need to pop a HorizontalStack (end of Map/Fork)
        // Note: We check currentBlock again because we might have just popped the vstack
        if (this.currentBlock.id === `hstack_${nodeId}`) {
            this.stack.pop();

            // Optional: Add a "Join" node after the parallel block
            this.addNode("genericAgentNode", step, "Join", { variant: "pill" });
        }
    }
}
