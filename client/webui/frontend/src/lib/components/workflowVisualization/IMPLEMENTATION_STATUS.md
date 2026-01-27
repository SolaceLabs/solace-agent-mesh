# Workflow Visualization - Expression Highlighting Feature

## Overview

This document tracks the implementation of expression-based node highlighting in the workflow visualization. When users hover over expressions (like `{{node_a.output.field}}` or `{{workflow.input.value}}`), the referenced source nodes are highlighted in the diagram.

## Status: Complete

## Feature Summary

### Expression Highlighting
- Hovering over condition pills (switch cases) highlights referenced nodes
- Hovering over input mapping values in the detail panel highlights referenced nodes
- Multiple node references in a single expression highlight all nodes simultaneously
- `workflow.input.xxx` expressions highlight the Start node (`__start__`)
- Highlighting uses an amber glow effect for visibility

## Files Created

### `utils/expressionParser.ts`
Expression parsing utility with functions:
- `extractNodeReferences(expression)` - Parses `{{...}}` templates and extracts node IDs
- `validateNodeReferences(refs, knownIds)` - Filters to only valid nodes in the workflow
- `getValidNodeReferences(expression, knownIds)` - Convenience combo function
- `extractNodeIdsFromConfig(config)` - Extracts all node IDs from a workflow config

Key behavior:
- Matches patterns like `{{node_id.output.field}}` or `{{node_id.input.field}}`
- Maps `workflow.input.xxx` to `__start__` (the Start node's internal ID)

### `InputMappingViewer.tsx`
Custom component for displaying input mappings with hover highlighting:
- Renders key-value pairs with JSON-like syntax highlighting
- Detects values containing `{{...}}` expressions
- Shows subtle amber hover effect on hoverable values
- Triggers node highlighting on hover via `onHighlightNodes` callback
- Supports nested objects and arrays

## Files Modified

### `utils/types.ts`
Added shared CSS class constants:
```typescript
export const NODE_HIGHLIGHT_CLASSES = "ring-2 ring-amber-400 ring-offset-2 shadow-lg shadow-amber-200/50 dark:ring-amber-500 dark:ring-offset-gray-900 dark:shadow-amber-500/30";

export const NODE_ID_BADGE_CLASSES = "absolute -bottom-2 left-1/2 -translate-x-1/2 rounded bg-gray-700 px-2 py-0.5 font-mono text-xs text-gray-100 opacity-0 transition-opacity duration-[750ms] ease-in group-hover:opacity-100 group-hover:duration-75 group-hover:ease-out dark:bg-gray-600";

export const NODE_SELECTED_CLASSES = {
    BLUE: "ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-900",
    BLUE_COMPACT: "ring-2 ring-blue-500 ring-offset-1 dark:ring-offset-gray-900",
    PURPLE: "ring-2 ring-purple-500 ring-offset-2 dark:ring-offset-gray-900",
    TEAL: "ring-2 ring-teal-500 ring-offset-2 dark:ring-offset-gray-900",
    INDIGO: "ring-2 ring-indigo-500 ring-offset-2 dark:ring-offset-gray-900",
};
```

Also added to `NodeProps` interface:
- `isHighlighted?: boolean`
- `onHighlightNodes?: (nodeIds: string[]) => void`
- `knownNodeIds?: Set<string>`

### `WorkflowDiagram.tsx`
- Added support for controlled highlighting via optional props:
  - `highlightedNodeIds` - Set of node IDs to highlight
  - `onHighlightNodes` - Callback when highlight changes
  - `knownNodeIds` - Pre-computed set of valid node IDs
- Falls back to internal state if controlled props not provided

### `WorkflowNodeRenderer.tsx`
- Accepts new props: `highlightedNodeIds`, `onHighlightNodes`, `knownNodeIds`
- Computes `isHighlighted` for each node and passes it down

### `WorkflowVisualizationPage.tsx`
- Manages `highlightedNodeIds` state at page level
- Computes `knownNodeIds` from workflow config
- Passes highlighting props to both `WorkflowDiagram` and `WorkflowNodeDetailPanel`

### `WorkflowNodeDetailPanel.tsx`
- Added `onHighlightNodes` and `knownNodeIds` props
- Uses `InputMappingViewer` instead of `JSONViewer` for input mappings

### Node Components (all use shared constants)
Updated to use centralized styling constants:

| Component | Selection Class | Has Highlight |
|-----------|----------------|---------------|
| `AgentNode.tsx` | `NODE_SELECTED_CLASSES.BLUE` | Yes |
| `StartNode.tsx` | `NODE_SELECTED_CLASSES.BLUE` | Yes |
| `EndNode.tsx` | `NODE_SELECTED_CLASSES.BLUE` | No |
| `WorkflowRefNode.tsx` | `NODE_SELECTED_CLASSES.PURPLE` | Yes |
| `SwitchNode.tsx` | `NODE_SELECTED_CLASSES.PURPLE` | Yes |
| `LoopNode.tsx` | `NODE_SELECTED_CLASSES.TEAL` | Yes |
| `MapNode.tsx` | `NODE_SELECTED_CLASSES.INDIGO` | Yes |
| `ConditionPillNode.tsx` | `NODE_SELECTED_CLASSES.BLUE_COMPACT` | No (triggers highlighting) |

### `nodes/ConditionPillNode.tsx`
- Added `handleMouseEnter` - extracts node refs from expression and triggers highlighting
- Added `handleMouseLeave` - clears highlighting

## Architecture

```
WorkflowVisualizationPage (manages highlightedNodeIds state)
├── WorkflowDiagram
│   └── WorkflowNodeRenderer
│       ├── AgentNode (receives isHighlighted)
│       ├── StartNode (receives isHighlighted)
│       ├── ConditionPillNode (triggers onHighlightNodes on hover)
│       └── ... other nodes
└── WorkflowNodeDetailPanel
    └── InputMappingViewer (triggers onHighlightNodes on hover)
```

## How It Works

1. User hovers over an expression (condition pill or input mapping value)
2. `expressionParser.extractNodeReferences()` parses the expression
3. Node IDs are validated against `knownNodeIds`
4. `onHighlightNodes(nodeIds)` is called, bubbling up to page level
5. Page updates `highlightedNodeIds` state
6. State flows down to `WorkflowDiagram` and node components
7. Nodes with matching IDs receive `isHighlighted: true`
8. Highlighted nodes render with amber glow effect

## Future Enhancements

Potential areas for extension:
- Highlight expressions in loop conditions (`while:` field in LoopNode)
- Highlight expressions in map items field
- Add highlighting to switch case conditions in the detail panel
- Visual indicator showing which expression triggered the highlight
