# PR 7: Frontend - Visualization (LAST)

## Overview

This PR adds **ALL frontend changes** for workflow visualization. It includes event processing, providers, the layout engine, and all React components for rendering workflows. **This PR is intentionally last** so the reviewer can test full workflow execution end-to-end.

## Branch Information

- **Branch Name:** `pr/workflows-7-frontend`
- **Target:** `pr/workflows-6-integration`

**Note:** At this point, the full backend is in place. Reviewers can pull this branch and test real workflow execution to validate the visualization.

## Files Changed

### Event Processing & Providers

#### `client/webui/frontend/src/lib/components/activities/index.ts`

Exports for activity components including workflow visualization.

#### `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts`

Processes A2A events into `VisualizerStep` objects:

| Event Type | Processing |
|------------|------------|
| `WORKFLOW_EXECUTION_START` | Create workflow container step |
| `WORKFLOW_NODE_EXECUTION_START` | Create node step with type info |
| `WORKFLOW_NODE_EXECUTION_RESULT` | Update node with result |
| `WORKFLOW_MAP_PROGRESS` | Update map node progress |

#### `client/webui/frontend/src/lib/components/activities/VisualizerStepCard.tsx`

Step card component for displaying individual execution steps.

#### `client/webui/frontend/src/lib/providers/*.tsx`

Provider updates for workflow state management:
- `ChatProvider.tsx`: Workflow message handling
- `TaskProvider.tsx`: Workflow task tracking

### Layout Engine

#### `client/webui/frontend/src/lib/components/activities/FlowChart/utils/layoutEngine.ts`

The layout engine (~1,450 lines) transforms execution events into positioned nodes:

| Function | Purpose |
|----------|---------|
| `processSteps()` | Build tree structure from events |
| `calculateLayout()` | Assign positions and dimensions |
| `calculateEdges()` | Compute connection paths |
| `layoutWorkflowGroup()` | Layout workflow container |
| `layoutMapNode()` | Layout map iterations |
| `layoutLoopNode()` | Layout loop iterations |

**Layout Algorithm:**
```
VisualizerStep[] (events)
        │
        ▼
   processSteps()     → Build parent-child relationships
        │
        ▼
   calculateLayout()  → Compute x, y, width, height
        │
        ▼
   calculateEdges()   → Generate SVG path data
        │
        ▼
   LayoutResult { nodes, edges, totalWidth, totalHeight }
```

#### `client/webui/frontend/src/lib/components/activities/FlowChart/utils/types.ts`

TypeScript type definitions:

```typescript
interface LayoutNode {
  id: string;
  type: NodeType;
  x: number;
  y: number;
  width: number;
  height: number;
  status: Status;
  children?: LayoutNode[];
  // ...
}

interface LayoutEdge {
  id: string;
  source: string;
  target: string;
  path: string;
  // ...
}
```

#### `client/webui/frontend/src/lib/components/activities/FlowChart/utils/nodeDetailsHelper.ts`

Helper functions for extracting node details (~400 lines):
- Extract input/output data
- Format timing information
- Parse error details
- Resolve artifact references

### Main Components

#### `client/webui/frontend/src/lib/components/activities/FlowChart/FlowChartPanel.tsx`

Main panel component (~175 lines):
- Container for workflow visualization
- Handles zoom/pan controls
- Manages selected node state
- Renders NodeDetailsCard sidebar

#### `client/webui/frontend/src/lib/components/activities/FlowChart/WorkflowRenderer.tsx`

SVG renderer component (~360 lines):
- Renders positioned nodes
- Renders edge connections
- Handles node selection
- Manages viewport transforms

#### `client/webui/frontend/src/lib/components/activities/FlowChart/EdgeLayer.tsx`

Edge rendering component (~170 lines):
- SVG path generation
- Animated connection lines
- Different styles for different edge types

#### `client/webui/frontend/src/lib/components/activities/FlowChart/NodeDetailsCard.tsx`

Details sidebar (~1,000 lines):
- Input/output data display
- Timing information
- Error details
- Artifact links
- JSON viewer for complex data

### Node Components

Each node type has a dedicated React component:

| Component | File | Purpose |
|-----------|------|---------|
| `AgentNode` | `nodes/AgentNode.tsx` | Agent invocation (~290 lines) |
| `UserNode` | `nodes/UserNode.tsx` | User input node |
| `ToolNode` | `nodes/ToolNode.tsx` | Tool invocation |
| `LLMNode` | `nodes/LLMNode.tsx` | LLM call |
| `ConditionalNode` | `nodes/ConditionalNode.tsx` | If/else decision (~65 lines) |
| `SwitchNode` | `nodes/SwitchNode.tsx` | Multi-way decision (~70 lines) |
| `MapNode` | `nodes/MapNode.tsx` | Parallel iteration (~175 lines) |
| `LoopNode` | `nodes/LoopNode.tsx` | While iteration (~160 lines) |
| `WorkflowGroup` | `nodes/WorkflowGroup.tsx` | Container for nested items (~375 lines) |

### Type Definitions

#### `client/webui/frontend/src/lib/types/activities.ts`

Activity type definitions for workflow events.

## Key Concepts

### Layout Algorithm

The layout engine handles complex scenarios:

1. **Nested agents**: Workflows calling agents calling tools
2. **Parallel execution**: Map iterations rendered side-by-side
3. **Dynamic updates**: Nodes completing in real-time
4. **Collapse/expand**: Complex workflows can be collapsed

### Node Visual Styles

| Node Type | Visual Style |
|-----------|--------------|
| Agent | Card with header, status indicator |
| Conditional | Diamond shape |
| Switch | Diamond with multiple outputs |
| Map | Container with iteration count |
| Loop | Container with iteration info |
| Workflow | Bordered group container |

### Status Colors

```typescript
const statusColors = {
  running: 'blue',
  completed: 'green',
  failed: 'red',
  skipped: 'gray',
  pending: 'gray',
};
```

### Real-time Updates

The visualization updates as events arrive:
1. `WORKFLOW_NODE_EXECUTION_START` → Node appears as "running"
2. `WORKFLOW_MAP_PROGRESS` → Progress indicator updates
3. `WORKFLOW_NODE_EXECUTION_RESULT` → Node status changes

## Testing Guide

Since this is the last PR, reviewers can test end-to-end:

1. **Start the backend** with a workflow configured
2. **Open the WebUI** and navigate to a chat
3. **Invoke the workflow** via chat or direct API
4. **Observe visualization**:
   - Workflow container appears
   - Nodes appear as they start
   - Status updates in real-time
   - Click nodes to see details
