# Workflow Graph Layout Engine

This directory contains the new hierarchical layout engine for the Workflow Graph.

## Architecture

The layout engine moves away from a linear "painter's algorithm" (calculating absolute coordinates while iterating events) to a **Box Model** approach.

### 1. Layout Blocks (`LayoutBlock.ts`)

The core unit is a `LayoutBlock`. It represents a rectangular region in the graph.
Blocks form a tree structure.

*   **`LeafBlock`**: Represents a visible Node (Agent, Tool, etc.). Has fixed dimensions.
*   **`VerticalStackBlock`**: Stacks its children vertically. Used for sequential execution traces.
*   **`HorizontalStackBlock`**: Stacks its children horizontally. Used for parallel execution (e.g., Map nodes).
*   **`GroupBlock`**: Wraps a child block (usually a stack) with a visual "Group Node" container (padding + border).

### 2. The Layout Process

The layout process has three phases:

1.  **Tree Construction (`BlockBuilder.ts`)**:
    *   Iterate through the linear `VisualizerStep` array.
    *   Construct a tree of `LayoutBlock`s.
    *   Maintain a stack of active container blocks to handle nesting (Workflows, Subflows).

2.  **Measurement (`measure()`)**:
    *   Traverse the tree **bottom-up**.
    *   Each block calculates its `width` and `height` based on its children and spacing/padding.
    *   Container blocks expand to fit their contents.

3.  **Positioning (`layout()`)**:
    *   Traverse the tree **top-down**.
    *   Assign absolute `x` and `y` coordinates to each block based on the parent's position and the block's layout logic (stacking direction).

### 3. Rendering

After the layout pass, we traverse the tree to collect all `Node` objects with their final calculated positions. Edges are then generated based on the logical connections between steps.

## Usage

```typescript
const builder = new BlockBuilder();
const rootBlock = builder.build(steps);

// Calculate dimensions
rootBlock.measure();

// Assign positions (starting at 0,0)
rootBlock.layout(0, 0);

// Get React Flow nodes
const nodes = rootBlock.collectNodes();
```
