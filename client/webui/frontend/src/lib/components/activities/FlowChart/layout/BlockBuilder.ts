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

    constructor() {
        this.root = new VerticalStackBlock("root");
        this.stack = [this.root];
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
                this.addNode("userNode", step, "User");
                break;
            case "AGENT_LLM_CALL":
                this.addNode("llmNode", step, "LLM");
                break;
            case "AGENT_TOOL_INVOCATION_START":
                this.handleToolInvocation(step);
                break;
            case "AGENT_TOOL_EXECUTION_RESULT":
                this.handleToolResult(step);
                break;
            case "AGENT_RESPONSE_TEXT":
                // Only add user node for root level responses (Orchestrator -> User)
                if (this.stack.length === 1 && !step.isSubTaskStep) {
                    this.addNode("userNode", step, "User");
                }
                break;
            case "WORKFLOW_EXECUTION_START":
                this.startGroup("workflow", step, step.data.workflowExecutionStart?.workflowName || "Workflow");
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

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private addNode(type: string, step: VisualizerStep, label: string, data: any = {}) {
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
        
        // Create edge from last node
        if (this.lastNodeId) {
            this.createEdge(this.lastNodeId, nodeId);
        }
        this.lastNodeId = nodeId;
    }

    private createEdge(source: string, target: string) {
        const edgeId = `e_${source}_${target}`;
        this.edges.push({
            id: edgeId,
            source: source,
            target: target,
            type: "defaultFlowEdge",
            animated: true, // Default to animated for now
        });
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
            this.startGroup("subflow", step, peerName);
        } else {
            const toolName = step.data.toolInvocationStart?.toolName || target;
            this.addNode("genericToolNode", step, toolName);
        }
    }

    private handleToolResult(step: VisualizerStep) {
        const isPeer = step.data.toolResult?.isPeerResponse || (step.source && (step.source.startsWith("peer_") || step.source.startsWith("workflow_")));

        if (isPeer) {
            this.endGroup();
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
            this.addNode("genericAgentNode", step, label, { variant: "pill" });

            const hStack = new HorizontalStackBlock(`hstack_${nodeId}`);
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
