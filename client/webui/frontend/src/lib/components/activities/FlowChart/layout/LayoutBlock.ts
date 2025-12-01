import type { Node } from "@xyflow/react";
import { NODE_HEIGHT, NODE_WIDTH, VERTICAL_SPACING, HORIZONTAL_SPACING, GROUP_PADDING_X, GROUP_PADDING_Y } from "./constants";

export abstract class LayoutBlock {
    id: string;
    parent?: LayoutBlock;
    children: LayoutBlock[] = [];
    
    // Dimensions (calculated by measure)
    width: number = 0;
    height: number = 0;
    
    // Relative Position (calculated by layout)
    x: number = 0;
    y: number = 0;

    // The React Flow node data associated with this block (if any)
    nodePayload?: Node;
    
    // The ID of the node that logically "starts" this block (e.g. Map node)
    anchorNodeId?: string;

    constructor(id: string, nodePayload?: Node) {
        this.id = id;
        this.nodePayload = nodePayload;
    }

    addChild(block: LayoutBlock) {
        block.parent = this;
        this.children.push(block);
    }

    abstract measure(): void;
    abstract layout(): void;
    
    resolveAbsolutePositions(parentX: number, parentY: number): void {
        console.log(`[LayoutBlock] Resolving absolute position for ${this.id}: parent(${parentX}, ${parentY}) + rel(${this.x}, ${this.y})`);
        const absX = parentX + this.x;
        const absY = parentY + this.y;
        
        if (this.nodePayload) {
            this.nodePayload.position = { x: absX, y: absY };
            
            // Update dimensions in style for ALL blocks that have a payload
            // This ensures stretched agents get their new height rendered
             this.nodePayload.style = {
                ...this.nodePayload.style,
                width: `${this.width}px`,
                height: `${this.height}px`,
            };
        }
        
        for (const child of this.children) {
            child.resolveAbsolutePositions(absX, absY);
        }
    }
    
    collectNodes(nodes: Node[] = []): Node[] {
        if (this.nodePayload) {
            nodes.push(this.nodePayload);
        }
        for (const child of this.children) {
            child.collectNodes(nodes);
        }
        return nodes;
    }
}

export class LeafBlock extends LayoutBlock {
    measure(): void {
        this.width = this.nodePayload?.measured?.width ?? 
                     (parseInt(this.nodePayload?.style?.width?.toString() || "0") || 
                     NODE_WIDTH);
                     
        this.height = this.nodePayload?.measured?.height ?? 
                      (parseInt(this.nodePayload?.style?.height?.toString() || "0") || 
                      NODE_HEIGHT);
        console.log(`[LeafBlock] ${this.id} measured: ${this.width}x${this.height}`);
    }

    layout(): void {
        // Leaf nodes don't layout children
    }
}

export class VerticalStackBlock extends LayoutBlock {
    spacing: number = VERTICAL_SPACING;

    measure(): void {
        console.log(`[VerticalStackBlock] Measuring ${this.id}`);
        this.width = 0;
        this.height = 0;
        
        for (const child of this.children) {
            child.measure();
            this.width = Math.max(this.width, child.width);
            this.height += child.height;
        }
        
        if (this.children.length > 1) {
            this.height += (this.children.length - 1) * this.spacing;
        }
        console.log(`[VerticalStackBlock] ${this.id} measured: ${this.width}x${this.height}`);
    }

    layout(): void {
        console.log(`[VerticalStackBlock] Layout ${this.id}`);
        let currentY = 0;
        for (const child of this.children) {
            child.x = 0; // Align left
            child.y = currentY;
            child.layout();
            currentY += child.height + this.spacing;
        }
    }
}

export class HorizontalStackBlock extends LayoutBlock {
    spacing: number = HORIZONTAL_SPACING;

    measure(): void {
        console.log(`[HorizontalStackBlock] Measuring ${this.id}`);
        this.width = 0;
        this.height = 0;

        for (const child of this.children) {
            child.measure();
            this.height = Math.max(this.height, child.height);
            this.width += child.width;
        }

        if (this.children.length > 1) {
            this.width += (this.children.length - 1) * this.spacing;
        }

        // Stretch the first child (Agent) to match the row height
        if (this.children.length > 0) {
             const firstChild = this.children[0];
             if (firstChild instanceof LeafBlock && 
                 (firstChild.nodePayload?.type === 'orchestratorNode' || firstChild.nodePayload?.type === 'genericAgentNode')) {
                 firstChild.height = this.height;
             }
        }

        console.log(`[HorizontalStackBlock] ${this.id} measured: ${this.width}x${this.height}`);
    }

    layout(): void {
        console.log(`[HorizontalStackBlock] Layout ${this.id}`);
        let currentX = 0;
        for (const child of this.children) {
            child.x = currentX;
            child.y = 0; // Align top
            child.layout();
            currentX += child.width + this.spacing;
        }
    }
}

export class GroupBlock extends LayoutBlock {
    paddingX: number = GROUP_PADDING_X;
    paddingY: number = GROUP_PADDING_Y;
    
    measure(): void {
        console.log(`[GroupBlock] Measuring ${this.id}`);
        let contentWidth = 0;
        let contentHeight = 0;

        for (const child of this.children) {
            child.measure();
            contentWidth = Math.max(contentWidth, child.width);
            contentHeight = Math.max(contentHeight, child.height); 
        }

        this.width = contentWidth + (this.paddingX * 2);
        this.height = contentHeight + (this.paddingY * 2);
        
        this.width = Math.max(this.width, 200); 
        this.height = Math.max(this.height, 100);
        console.log(`[GroupBlock] ${this.id} measured: ${this.width}x${this.height}`);
    }

    layout(): void {
        console.log(`[GroupBlock] Layout ${this.id}`);
        const currentX = this.paddingX;
        const currentY = this.paddingY;
        
        for (const child of this.children) {
            child.x = currentX;
            child.y = currentY;
            child.layout();
        }
    }
}
