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

    // Flag to indicate this block should be pulled up to align with the top of the previous sibling
    pullUp: boolean = false;
    
    // The block that logically triggered this block (for layout dependency)
    sourceBlock?: LayoutBlock;

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

export class TimelineBlock extends LayoutBlock {
    spacing: number = VERTICAL_SPACING;

    measure(): void {
        this.width = 0;
        this.height = 0;
        
        // Simulate layout to determine height and width
        const laneY: Record<number, number> = {};
        
        for (const child of this.children) {
            child.measure();
            
            // Calculate max width including lane offset
            const childRight = child.laneOffset + child.width;
            this.width = Math.max(this.width, childRight);

            const lane = child.laneOffset;
            const laneBottom = laneY[lane] || 0;
            
            // Use reduced spacing for pulled up items (tools)
            const currentSpacing = child.pullUp ? this.spacing / 2 : this.spacing;
            
            // Simple height estimation for measure phase
            laneY[lane] = laneBottom + child.height + currentSpacing;
        }
        
        this.height = Math.max(...Object.values(laneY), 0);
    }

    layout(offsetX: number, offsetY: number): void {
        this.x = offsetX;
        this.y = offsetY;

        const laneY: Record<number, number> = {}; // laneOffset -> currentY
        let maxWidth = 0;

        for (const child of this.children) {
            const lane = child.laneOffset;
            
            // Use reduced spacing for pulled up items (tools)
            const currentSpacing = child.pullUp ? this.spacing / 2 : this.spacing;
            
            // Determine Y based on source dependency
            let dependencyY = offsetY;
            if (child.sourceBlock) {
                // sourceBlock.y is absolute. We need to ensure it's been laid out.
                // Assuming chronological order, it should be.
                dependencyY = child.sourceBlock.y + child.sourceBlock.height + this.spacing;
            }

            // Determine Y based on lane availability
            const laneBottom = laneY[lane] || offsetY;
            
            let y = Math.max(laneBottom, dependencyY);
            
            // PullUp logic: Align with source top if requested
            if (child.pullUp && child.sourceBlock) {
                // We want to start at the same Y as the source
                // But we must still respect laneBottom (can't overlap previous item in same lane)
                y = Math.max(laneBottom, child.sourceBlock.y);
            }

            child.layout(offsetX, y);
            
            // Update lane tracker
            laneY[lane] = y + child.height + currentSpacing;
            
            // Update max width
            const childRight = child.laneOffset + child.width;
            maxWidth = Math.max(maxWidth, childRight);
        }
        
        // Update final height based on actual layout
        const maxBottom = Math.max(...Object.values(laneY), offsetY);
        this.height = maxBottom - offsetY;
        this.width = maxWidth;
    }
}

// Alias for backward compatibility
export class VerticalStackBlock extends TimelineBlock {}

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
        let maxHeight = 0;

        for (const child of this.children) {
            child.layout(currentX, offsetY);
            currentX += child.width + this.spacing;
            maxHeight = Math.max(maxHeight, child.height);
        }

        this.height = maxHeight;
        if (this.children.length > 0) {
            this.width = currentX - this.spacing - offsetX;
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
        
        let maxChildBottom = currentY;
        let maxChildRight = currentX;

        for (const child of this.children) {
            child.layout(currentX, currentY);
            
            // Track bounds of children to update group size if needed
            maxChildBottom = Math.max(maxChildBottom, child.y + child.height);
            maxChildRight = Math.max(maxChildRight, child.x + child.width);
        }

        // Update dimensions based on actual layout to ensure container fits children
        this.height = maxChildBottom - this.y + this.paddingY;
        this.width = maxChildRight - this.x + this.paddingX;
        
        // Ensure minimum size
        this.width = Math.max(this.width, 200); 
        this.height = Math.max(this.height, 100);
    }
}
