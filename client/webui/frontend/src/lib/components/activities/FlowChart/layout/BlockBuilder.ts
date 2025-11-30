import type { VisualizerStep } from "@/lib/types";
import { LayoutBlock, VerticalStackBlock, LeafBlock, GroupBlock } from "./LayoutBlock";
import type { Node } from "@xyflow/react";

/**
 * Responsible for converting a linear stream of VisualizerSteps into a hierarchical LayoutBlock tree.
 */
export class BlockBuilder {
    private root: VerticalStackBlock;
    private stack: LayoutBlock[];
    private nodeCounter: number = 0;

    constructor() {
        this.root = new VerticalStackBlock("root");
        this.stack = [this.root];
    }

    public build(steps: VisualizerStep[]): LayoutBlock {
        for (const step of steps) {
            this.processStep(step);
        }
        return this.root;
    }

    private get currentBlock(): LayoutBlock {
        return this.stack[this.stack.length - 1];
    }

    private processStep(step: VisualizerStep) {
        // This switch statement will eventually contain the logic migrated from taskToFlowData.ts
        // For now, it demonstrates the structure.
        switch (step.type) {
            case "USER_REQUEST":
                this.addNode("userNode", step);
                break;
            case "AGENT_LLM_CALL":
                this.addNode("llmNode", step);
                break;
            case "WORKFLOW_EXECUTION_START":
                this.startGroup("workflow", step);
                break;
            case "WORKFLOW_EXECUTION_RESULT":
                this.endGroup();
                break;
            // Add other cases as migration proceeds
        }
    }

    private addNode(type: string, step: VisualizerStep) {
        const nodeId = `${type}_${this.nodeCounter++}`;
        const node: Node = {
            id: nodeId,
            type: type,
            position: { x: 0, y: 0 }, // Will be set by layout engine
            data: { label: step.title, visualizerStepId: step.id }
        };
        const block = new LeafBlock(nodeId, node);
        this.currentBlock.addChild(block);
    }

    private startGroup(type: string, step: VisualizerStep) {
        const groupId = `group_${this.nodeCounter++}`;
        const groupNode: Node = {
            id: groupId,
            type: "group",
            position: { x: 0, y: 0 },
            data: { label: step.title },
            style: { width: 0, height: 0 } // Will be set by layout engine
        };
        
        const groupBlock = new GroupBlock(groupId, groupNode);
        this.currentBlock.addChild(groupBlock);
        
        // A group usually contains a vertical stack of items
        const innerStack = new VerticalStackBlock(`${groupId}_stack`);
        groupBlock.addChild(innerStack);
        
        // Push the inner stack so subsequent nodes are added to it
        this.stack.push(innerStack);
    }

    private endGroup() {
        // Ensure we don't pop the root
        if (this.stack.length > 1) {
            this.stack.pop();
        }
    }
}
