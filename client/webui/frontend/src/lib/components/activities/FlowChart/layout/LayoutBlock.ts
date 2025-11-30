import type { Node } from "@xyflow/react";
import { NODE_HEIGHT, NODE_WIDTH, VERTICAL_SPACING, HORIZONTAL_SPACING, GROUP_PADDING_X, GROUP_PADDING_Y } from "./constants";

export abstract class LayoutBlock {
    id: string;
    parent?: LayoutBlock;
    children: LayoutBlock[] = [];
    
    // Dimensions (calculated by measure)
    width: number = 0;
    height: number = 0;
    
    // Position (calculated by layout)
    x: number = 0;
    y: number = 0;
    
    // Offset for swimlanes (relative to parent)
    laneOffset: number = 0;

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
    abstract layout(offsetX: number, offsetY: number): void;
    
    // Helper to collect all nodes recursively after layout
    collectNodes(nodes: Node[] = []): Node[] {
        if (this.nodePayload) {
            // Update the payload position with the calculated layout position
            this.nodePayload.position = { x: this.x, y: this.y };
            
            // If this block represents a group, we might need to update style dimensions
            if (this.nodePayload.type === 'group') {
                 this.nodePayload.style = {
                    ...this.nodePayload.style,
                    width: `${this.width}px`,
                    height: `${this.height}px`,
                };
            }
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
        // Use fixed dimensions or dimensions from payload if available
        // We check measured dimensions first (if React Flow has rendered it), then style, then defaults
        this.width = this.nodePayload?.measured?.width ?? 
                     (parseInt(this.nodePayload?.style?.width?.toString() || "0") || 
                     NODE_WIDTH);
                     
        this.height = this.nodePayload?.measured?.height ?? 
                      (parseInt(this.nodePayload?.style?.height?.toString() || "0") || 
                      NODE_HEIGHT);
    }

    layout(offsetX: number, offsetY: number): void {
        this.x = offsetX + this.laneOffset;
        this.y = offsetY;
    }
}

export class VerticalStackBlock extends LayoutBlock {
    spacing: number = VERTICAL_SPACING;

    measure(): void {
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
    }

    layout(offsetX: number, offsetY: number): void {
        this.x = offsetX;
        this.y = offsetY;

        let currentY = offsetY;
        for (const child of this.children) {
            // Align children to the left (offsetX)
            child.layout(offsetX, currentY);
            currentY += child.height + this.spacing;
        }
    }
}

export class HorizontalStackBlock extends LayoutBlock {
    spacing: number = HORIZONTAL_SPACING;

    measure(): void {
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
    }

    layout(offsetX: number, offsetY: number): void {
        this.x = offsetX;
        this.y = offsetY;

        let currentX = offsetX;
        for (const child of this.children) {
            child.layout(currentX, offsetY);
            currentX += child.width + this.spacing;
        }
    }
}

export class GroupBlock extends LayoutBlock {
    paddingX: number = GROUP_PADDING_X;
    paddingY: number = GROUP_PADDING_Y;
    
    measure(): void {
        // Measure children (usually just one VerticalStackBlock inside)
        let contentWidth = 0;
        let contentHeight = 0;

        for (const child of this.children) {
            child.measure();
            contentWidth = Math.max(contentWidth, child.width);
            contentHeight += child.height; 
        }

        this.width = contentWidth + (this.paddingX * 2);
        this.height = contentHeight + (this.paddingY * 2);
        
        // Ensure minimum size for the label visibility
        this.width = Math.max(this.width, 200); 
        this.height = Math.max(this.height, 100);
    }

    layout(offsetX: number, offsetY: number): void {
        this.x = offsetX + this.laneOffset;
        this.y = offsetY;

        // Layout children inside the padding
        let currentY = this.y + this.paddingY;
        let currentX = this.x + this.paddingX;
        
        for (const child of this.children) {
            child.layout(currentX, currentY);
            // If multiple children, they overlap in this simple implementation
            // GroupBlock should typically wrap a single StackBlock
        }
    }
}
