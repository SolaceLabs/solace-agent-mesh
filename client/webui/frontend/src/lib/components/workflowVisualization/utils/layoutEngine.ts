/**
 * Layout Engine for Workflow Visualization
 *
 * Converts WorkflowConfig to positioned LayoutNodes with edges
 */

import type { WorkflowConfig, WorkflowNodeConfig } from "@/lib/utils/agentUtils";
import type { LayoutNode, LayoutResult, Edge, WorkflowVisualNodeType } from "./types";
import { LAYOUT_CONSTANTS } from "./types";

const { NODE_WIDTHS, NODE_HEIGHTS, SPACING } = LAYOUT_CONSTANTS;

/**
 * Internal node representation during processing
 */
interface ProcessedNode {
    id: string;
    type: WorkflowNodeConfig["type"];
    config: WorkflowNodeConfig;
    dependsOn: string[];
    dependents: string[];
    level: number;
    isContainerChild: boolean; // True if this node is inside a map/loop
    containerParentId?: string;
}

/**
 * Main entry point: process workflow config into visual layout
 */
export function processWorkflowConfig(config: WorkflowConfig, collapsedNodes: Set<string> = new Set(), knownWorkflows: Set<string> = new Set()): LayoutResult {
    if (!config.nodes || config.nodes.length === 0) {
        return createEmptyLayout();
    }

    // Build processed nodes map
    const nodeMap = buildNodeMap(config.nodes);

    // Identify container children (nodes referenced by map/loop)
    markContainerChildren(nodeMap, config.nodes);

    // Build dependency graph
    buildDependencyGraph(nodeMap);

    // Copy container child dependents to their parent containers
    copyContainerChildDependents(nodeMap);

    // Assign levels via topological sort
    assignLevels(nodeMap);

    // Group nodes by level (excluding container children)
    const levelGroups = groupByLevel(nodeMap);

    // Create layout nodes
    const layoutNodes = createLayoutNodes(nodeMap, levelGroups, collapsedNodes, knownWorkflows);

    // Calculate positions (needs nodeMap for dependency-based positioning)
    const positioned = calculatePositions(layoutNodes, nodeMap);

    // Insert condition pill nodes for switch branches
    const withConditionPills = insertConditionPills(positioned, nodeMap);

    // Generate edges (with condition pill handling)
    const edges = generateEdges(withConditionPills, nodeMap);

    // Calculate total dimensions
    const { totalWidth, totalHeight } = calculateDimensions(withConditionPills);

    return {
        nodes: withConditionPills,
        edges,
        totalWidth,
        totalHeight,
    };
}

/**
 * Create empty layout with just start/end
 */
function createEmptyLayout(): LayoutResult {
    const startNode: LayoutNode = {
        id: "__start__",
        type: "start",
        data: { label: "Start" },
        x: 0,
        y: 0,
        width: NODE_WIDTHS.START,
        height: NODE_HEIGHTS.PILL,
        children: [],
    };

    const endNode: LayoutNode = {
        id: "__end__",
        type: "end",
        data: { label: "End" },
        x: 0,
        y: NODE_HEIGHTS.PILL + SPACING.VERTICAL,
        width: NODE_WIDTHS.END,
        height: NODE_HEIGHTS.PILL,
        children: [],
    };

    return {
        nodes: [startNode, endNode],
        edges: [
            {
                id: "start-end",
                source: "__start__",
                target: "__end__",
                sourceX: NODE_WIDTHS.START / 2,
                sourceY: NODE_HEIGHTS.PILL,
                targetX: NODE_WIDTHS.END / 2,
                targetY: NODE_HEIGHTS.PILL + SPACING.VERTICAL,
            },
        ],
        totalWidth: NODE_WIDTHS.START,
        totalHeight: NODE_HEIGHTS.PILL * 2 + SPACING.VERTICAL,
    };
}

/**
 * Build map of processed nodes
 */
function buildNodeMap(nodes: WorkflowNodeConfig[]): Map<string, ProcessedNode> {
    const nodeMap = new Map<string, ProcessedNode>();

    for (const node of nodes) {
        nodeMap.set(node.id, {
            id: node.id,
            type: node.type,
            config: node,
            dependsOn: node.depends_on || [],
            dependents: [],
            level: -1,
            isContainerChild: false,
        });
    }

    return nodeMap;
}

/**
 * Mark nodes that are children of map/loop containers
 * Also copies the child's dependents to the container so edges are drawn correctly
 */
function markContainerChildren(nodeMap: Map<string, ProcessedNode>, nodes: WorkflowNodeConfig[]): void {
    for (const node of nodes) {
        if ((node.type === "map" || node.type === "loop") && node.node) {
            const childNode = nodeMap.get(node.node);
            const containerNode = nodeMap.get(node.id);
            if (childNode && containerNode) {
                childNode.isContainerChild = true;
                childNode.containerParentId = node.id;
            }
        }
    }
}

/**
 * Copy dependents from container children to their parent containers
 * This must be called AFTER buildDependencyGraph
 */
function copyContainerChildDependents(nodeMap: Map<string, ProcessedNode>): void {
    for (const procNode of nodeMap.values()) {
        if (procNode.isContainerChild && procNode.containerParentId) {
            const containerNode = nodeMap.get(procNode.containerParentId);
            if (containerNode) {
                // Copy child's dependents to the container
                for (const depId of procNode.dependents) {
                    if (!containerNode.dependents.includes(depId)) {
                        containerNode.dependents.push(depId);
                    }
                }

                // Also update the dependent nodes to depend on the container instead of the child
                for (const depId of procNode.dependents) {
                    const depNode = nodeMap.get(depId);
                    if (depNode) {
                        // Replace the child reference with the container reference
                        const childIndex = depNode.dependsOn.indexOf(procNode.id);
                        if (childIndex !== -1) {
                            depNode.dependsOn[childIndex] = procNode.containerParentId;
                        }
                    }
                }
            }
        }
    }
}

/**
 * Build dependency relationships (bidirectional)
 */
function buildDependencyGraph(nodeMap: Map<string, ProcessedNode>): void {
    for (const node of nodeMap.values()) {
        for (const depId of node.dependsOn) {
            const depNode = nodeMap.get(depId);
            if (depNode) {
                depNode.dependents.push(node.id);
            }
        }
    }
}

/**
 * Assign levels using topological sort (BFS from roots)
 */
function assignLevels(nodeMap: Map<string, ProcessedNode>): void {
    // Find root nodes (no dependencies, not container children)
    const roots: string[] = [];
    for (const node of nodeMap.values()) {
        if (node.dependsOn.length === 0 && !node.isContainerChild) {
            roots.push(node.id);
            node.level = 0;
        }
    }

    // BFS to assign levels
    const queue = [...roots];
    while (queue.length > 0) {
        const currentId = queue.shift()!;
        const current = nodeMap.get(currentId)!;

        for (const depId of current.dependents) {
            const dep = nodeMap.get(depId);
            if (dep && !dep.isContainerChild) {
                // Level is max of all dependency levels + 1
                const newLevel = current.level + 1;
                if (dep.level < newLevel) {
                    dep.level = newLevel;
                    queue.push(depId);
                }
            }
        }
    }
}

/**
 * Group non-container-child nodes by level
 */
function groupByLevel(nodeMap: Map<string, ProcessedNode>): Map<number, ProcessedNode[]> {
    const groups = new Map<number, ProcessedNode[]>();

    for (const node of nodeMap.values()) {
        if (!node.isContainerChild && node.level >= 0) {
            if (!groups.has(node.level)) {
                groups.set(node.level, []);
            }
            groups.get(node.level)!.push(node);
        }
    }

    return groups;
}

/**
 * Create layout nodes from processed nodes
 */
function createLayoutNodes(nodeMap: Map<string, ProcessedNode>, levelGroups: Map<number, ProcessedNode[]>, collapsedNodes: Set<string>, knownWorkflows: Set<string>): LayoutNode[] {
    const layoutNodes: LayoutNode[] = [];

    // Add start node at level -1
    layoutNodes.push({
        id: "__start__",
        type: "start",
        data: { label: "Start" },
        x: 0,
        y: 0,
        width: NODE_WIDTHS.START,
        height: NODE_HEIGHTS.PILL,
        children: [],
        level: -1,
    });

    // Process each level
    const sortedLevels = Array.from(levelGroups.keys()).sort((a, b) => a - b);

    for (const level of sortedLevels) {
        const nodesAtLevel = levelGroups.get(level)!;

        for (const procNode of nodesAtLevel) {
            const layoutNode = createLayoutNode(procNode, nodeMap, collapsedNodes, knownWorkflows);
            layoutNode.level = level;
            layoutNodes.push(layoutNode);
        }
    }

    // Find the max level for the end node
    const maxLevel = sortedLevels.length > 0 ? sortedLevels[sortedLevels.length - 1] + 1 : 0;

    // Add end node
    layoutNodes.push({
        id: "__end__",
        type: "end",
        data: { label: "End" },
        x: 0,
        y: 0,
        width: NODE_WIDTHS.END,
        height: NODE_HEIGHTS.PILL,
        children: [],
        level: maxLevel,
    });

    return layoutNodes;
}

/**
 * Create a single layout node from processed node
 */
function createLayoutNode(procNode: ProcessedNode, nodeMap: Map<string, ProcessedNode>, collapsedNodes: Set<string>, knownWorkflows: Set<string>): LayoutNode {
    const config = procNode.config;
    const isCollapsed = collapsedNodes.has(procNode.id);

    // Determine if this is a workflow node
    // Either explicit type: "workflow" or an agent that's a known workflow
    const isWorkflowRef = config.type === "workflow" || (config.type === "agent" && !!config.agent_name && knownWorkflows.has(config.agent_name));

    // Get the workflow name from either workflow_name or agent_name
    const workflowName = config.type === "workflow" ? config.workflow_name : isWorkflowRef ? config.agent_name : undefined;

    const baseNode: LayoutNode = {
        id: procNode.id,
        type: getVisualNodeType(config.type, isWorkflowRef),
        data: {
            label: config.id,
            agentName: config.agent_name || config.workflow_name,
            workflowName: workflowName,
            originalConfig: config,
        },
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        children: [],
        isCollapsed,
    };

    // Type-specific processing
    switch (config.type) {
        case "agent":
            baseNode.width = isWorkflowRef ? NODE_WIDTHS.WORKFLOW : NODE_WIDTHS.AGENT;
            baseNode.height = NODE_HEIGHTS.AGENT;
            break;

        case "workflow":
            baseNode.width = NODE_WIDTHS.WORKFLOW;
            baseNode.height = NODE_HEIGHTS.AGENT;
            break;

        case "switch": {
            baseNode.data.cases = config.cases;
            baseNode.data.defaultCase = config.default;
            baseNode.branches = createSwitchBranches(config);

            // Calculate switch node height based on number of cases
            const numCases = (config.cases?.length || 0) + (config.default ? 1 : 0);
            const switchHeaderHeight = 44; // Header row height (SwitchNode.tsx line 29: px-4 py-3)
            const caseRowHeight = 28; // Height per case row (max of h-5 badge 20px or text with py-1 = 28px)
            const caseRowGap = 6; // Gap between rows (SwitchNode.tsx line 42: gap-1.5)
            const casesSectionPadding = 12; // Cases section padding (SwitchNode.tsx line 41: pb-3 bottom only)

            baseNode.width = NODE_WIDTHS.SWITCH_COLLAPSED;
            baseNode.height = numCases > 0 ? switchHeaderHeight + casesSectionPadding + numCases * caseRowHeight + (numCases - 1) * caseRowGap : NODE_HEIGHTS.AGENT;
            break;
        }

        case "map":
            baseNode.data.items = config.items;
            baseNode.data.childNodeId = config.node;

            // Get child node if exists
            if (config.node && !isCollapsed) {
                const childProc = nodeMap.get(config.node);
                if (childProc) {
                    const childLayout = createLayoutNode(childProc, nodeMap, collapsedNodes, knownWorkflows);
                    baseNode.children = [childLayout];
                }
            }

            // Calculate container dimensions
            // When collapsed, only the header is shown (no dotted container)
            baseNode.width = isCollapsed
                ? NODE_WIDTHS.SWITCH_COLLAPSED // Use standard node width when collapsed
                : Math.max(NODE_WIDTHS.MAP_MIN, calculateContainerWidth(baseNode.children));
            baseNode.height = isCollapsed ? NODE_HEIGHTS.CONTAINER_HEADER : NODE_HEIGHTS.CONTAINER_HEADER + calculateContainerContentHeight(baseNode.children);
            break;

        case "loop":
            {
                baseNode.data.condition = config.condition;
                baseNode.data.maxIterations = config.max_iterations;
                baseNode.data.childNodeId = config.node;

                // Get child node if exists
                if (config.node && !isCollapsed) {
                    const childProc = nodeMap.get(config.node);
                    if (childProc) {
                        const childLayout = createLayoutNode(childProc, nodeMap, collapsedNodes, knownWorkflows);
                        baseNode.children = [childLayout];
                    }
                }

                // Calculate container dimensions
                // When collapsed, only the header is shown (no dotted container)
                // When expanded and has condition/max_iterations, include extra row height
                const hasConditionRow = !!(config.condition || config.max_iterations);
                const loopHeaderHeight = NODE_HEIGHTS.CONTAINER_HEADER + (hasConditionRow && !isCollapsed ? NODE_HEIGHTS.LOOP_CONDITION_ROW : 0);

                baseNode.width = isCollapsed
                    ? NODE_WIDTHS.SWITCH_COLLAPSED // Use standard node width when collapsed
                    : Math.max(NODE_WIDTHS.LOOP_MIN, calculateContainerWidth(baseNode.children));
                baseNode.height = isCollapsed ? NODE_HEIGHTS.CONTAINER_HEADER : loopHeaderHeight + calculateContainerContentHeight(baseNode.children);
            }
            break;
    }

    return baseNode;
}

/**
 * Get visual node type from config type
 */
function getVisualNodeType(configType: WorkflowNodeConfig["type"], isWorkflow: boolean): WorkflowVisualNodeType {
    // Explicit workflow type
    if (configType === "workflow") {
        return "workflow";
    }
    // Agent that is actually a workflow (detected via knownWorkflows)
    if (configType === "agent" && isWorkflow) {
        return "workflow";
    }
    return configType as WorkflowVisualNodeType;
}

/**
 * Create branches for switch node
 */
function createSwitchBranches(config: WorkflowNodeConfig): LayoutNode["branches"] {
    const branches: LayoutNode["branches"] = [];

    // Add case branches
    if (config.cases) {
        for (let i = 0; i < config.cases.length; i++) {
            branches.push({
                label: `${i + 1}`,
                isDefault: false,
                nodes: [], // Branches are rendered separately based on dependencies
            });
        }
    }

    // Add default branch
    if (config.default) {
        branches.push({
            label: "default",
            isDefault: true,
            nodes: [],
        });
    }

    return branches;
}

/**
 * Calculate container width based on children
 */
function calculateContainerWidth(children: LayoutNode[]): number {
    if (children.length === 0) {
        return NODE_WIDTHS.MAP_MIN;
    }

    const childrenWidth = children.reduce((sum, child) => sum + child.width, 0);
    const gaps = Math.max(0, children.length - 1) * SPACING.HORIZONTAL;

    return childrenWidth + gaps + SPACING.CONTAINER_PADDING * 2;
}

/**
 * Calculate container content height
 */
function calculateContainerContentHeight(children: LayoutNode[]): number {
    if (children.length === 0) {
        return SPACING.CONTAINER_PADDING * 2;
    }

    const maxChildHeight = Math.max(...children.map(c => c.height));
    return maxChildHeight + SPACING.CONTAINER_PADDING * 2;
}

/**
 * Compute barycenter (average x position) of parent nodes
 */
function computeBarycenter(parentIds: string[], nodeById: Map<string, LayoutNode>): number {
    if (parentIds.length === 0) return 0;

    let sum = 0;
    let count = 0;
    for (const id of parentIds) {
        const parent = nodeById.get(id);
        if (parent) {
            sum += parent.x + parent.width / 2;
            count++;
        }
    }

    return count > 0 ? sum / count : 0;
}

/**
 * Calculate positions for all nodes using dependency-based positioning
 * Nodes are positioned below their dependencies to maintain branch alignment
 */
function calculatePositions(nodes: LayoutNode[], nodeMap: Map<string, ProcessedNode>): LayoutNode[] {
    if (nodes.length === 0) return nodes;

    // Build lookup maps
    const nodeById = new Map<string, LayoutNode>();
    const levelMap = new Map<number, LayoutNode[]>();

    for (const node of nodes) {
        nodeById.set(node.id, node);
        const level = node.level ?? 0;
        if (!levelMap.has(level)) {
            levelMap.set(level, []);
        }
        levelMap.get(level)!.push(node);
    }

    // Sort levels
    const sortedLevels = Array.from(levelMap.keys()).sort((a, b) => a - b);

    // Calculate height for each level (max height of nodes at that level)
    const levelHeights = new Map<number, number>();
    for (const level of sortedLevels) {
        const nodesAtLevel = levelMap.get(level)!;
        const maxHeight = Math.max(...nodesAtLevel.map(n => n.height));
        levelHeights.set(level, maxHeight);
    }

    // Identify levels that come after switch nodes (need extra spacing for condition pills)
    const levelsAfterSwitch = new Set<number>();
    for (const node of nodes) {
        if (node.type === "switch") {
            const nodeLevel = node.level ?? 0;
            // The next level after a switch needs extra spacing
            levelsAfterSwitch.add(nodeLevel + 1);
        }
    }

    // Calculate Y position for each level (with extra spacing after switches)
    const levelYPositions = new Map<number, number>();
    let currentY = 0;
    for (const level of sortedLevels) {
        levelYPositions.set(level, currentY);
        const levelHeight = levelHeights.get(level) || 0;
        // Use extra spacing if this level follows a switch node
        const spacing = levelsAfterSwitch.has(level + 1) ? SPACING.VERTICAL_BRANCH : SPACING.VERTICAL;
        currentY += levelHeight + spacing;
    }

    // First pass: Position root level nodes (level -1 for start, level 0 for roots)
    // Calculate total width needed for the first level of regular nodes
    const firstRegularLevel = sortedLevels.find(l => l >= 0) ?? 0;
    const firstLevelNodes = levelMap.get(firstRegularLevel) || [];
    const firstLevelWidth = firstLevelNodes.reduce((sum, n) => sum + n.width, 0) + Math.max(0, firstLevelNodes.length - 1) * SPACING.HORIZONTAL;

    // Position start node centered
    const startNode = nodeById.get("__start__");
    if (startNode) {
        const startLevel = startNode.level ?? -1;
        const levelY = levelYPositions.get(startLevel) || 0;
        const levelHeight = levelHeights.get(startLevel) || startNode.height;
        startNode.x = Math.max(firstLevelWidth, startNode.width) / 2 - startNode.width / 2;
        startNode.y = levelY + (levelHeight - startNode.height) / 2;
    }

    // Position first level of regular nodes
    let currentX = 0;
    for (const node of firstLevelNodes) {
        const levelY = levelYPositions.get(firstRegularLevel) || 0;
        const levelHeight = levelHeights.get(firstRegularLevel) || node.height;
        node.x = currentX;
        node.y = levelY + (levelHeight - node.height) / 2;
        currentX += node.width + SPACING.HORIZONTAL;

        // Position children within containers
        if (node.children.length > 0) {
            positionContainerChildren(node);
        }
    }

    // Second pass: Position subsequent levels based on dependencies
    // Group siblings (nodes with same parents) and spread them symmetrically
    for (const level of sortedLevels) {
        if (level <= firstRegularLevel) continue; // Already positioned

        const nodesAtLevel = levelMap.get(level)!;
        const levelY = levelYPositions.get(level) || 0;
        const levelHeight = levelHeights.get(level) || 0;

        // Sort nodes at this level by barycenter (average x position of parents)
        // This ensures nodes in the same branch are co-located
        nodesAtLevel.sort((a, b) => {
            if (a.id === "__end__") return 1; // End node goes last
            if (b.id === "__end__") return -1;

            const aProc = nodeMap.get(a.id);
            const bProc = nodeMap.get(b.id);
            if (!aProc || !bProc) return 0;

            const aBarycenter = computeBarycenter(aProc.dependsOn, nodeById);
            const bBarycenter = computeBarycenter(bProc.dependsOn, nodeById);

            return aBarycenter - bBarycenter;
        });

        // Group nodes by their parent(s) to identify siblings
        const siblingGroups = new Map<string, LayoutNode[]>();

        for (const node of nodesAtLevel) {
            if (node.id === "__end__") continue; // Handle end node separately

            const procNode = nodeMap.get(node.id);
            if (!procNode) continue;

            // Create a key from sorted dependency IDs
            const parentKey = [...procNode.dependsOn].sort().join(",");
            if (!siblingGroups.has(parentKey)) {
                siblingGroups.set(parentKey, []);
            }
            siblingGroups.get(parentKey)!.push(node);
        }

        // Calculate ideal center and width for each sibling group
        const groupInfos: Array<{
            parentKey: string;
            siblings: LayoutNode[];
            idealCenterX: number;
            totalWidth: number;
        }> = [];

        for (const [parentKey, siblings] of siblingGroups) {
            const parentIds = parentKey.split(",").filter(id => id.length > 0);
            const parents = parentIds.map(id => nodeById.get(id)).filter((n): n is LayoutNode => n !== undefined);

            // Calculate the ideal center point based on parent(s)
            let idealCenterX: number;
            if (parents.length === 0) {
                idealCenterX = firstLevelWidth / 2;
            } else if (parents.length === 1) {
                idealCenterX = parents[0].x + parents[0].width / 2;
            } else {
                const minX = Math.min(...parents.map(p => p.x));
                const maxX = Math.max(...parents.map(p => p.x + p.width));
                idealCenterX = (minX + maxX) / 2;
            }

            // Calculate total width of this sibling group
            const siblingsWidth = siblings.reduce((sum, s) => sum + s.width, 0);
            const gaps = Math.max(0, siblings.length - 1) * SPACING.HORIZONTAL;
            const totalWidth = siblingsWidth + gaps;

            groupInfos.push({ parentKey, siblings, idealCenterX, totalWidth });
        }

        // Sort sibling groups by their ideal center position (left to right)
        groupInfos.sort((a, b) => a.idealCenterX - b.idealCenterX);

        // Position each sibling group, ensuring no overlap between groups
        let nextAvailableX = -Infinity; // Track the right edge of the last positioned group

        for (const groupInfo of groupInfos) {
            const { siblings, idealCenterX, totalWidth } = groupInfo;

            // Calculate the ideal start position (centered below parents)
            const idealStartX = idealCenterX - totalWidth / 2;

            // Ensure this group doesn't overlap with the previous group
            const actualStartX = Math.max(idealStartX, nextAvailableX);

            // Position siblings within the group
            let currentX = actualStartX;
            for (const node of siblings) {
                node.x = currentX;
                node.y = levelY + (levelHeight - node.height) / 2;
                currentX += node.width + SPACING.HORIZONTAL;

                if (node.children.length > 0) {
                    positionContainerChildren(node);
                }
            }

            // Update the next available x position (right edge of this group + gap)
            nextAvailableX = actualStartX + totalWidth + SPACING.HORIZONTAL;
        }

        // Handle end node separately
        const endNode = nodesAtLevel.find(n => n.id === "__end__");
        if (endNode) {
            const endDependencies = findEndNodeDependencies(nodeMap, nodeById);
            if (endDependencies.length > 0) {
                const avgX = endDependencies.reduce((sum, dep) => sum + dep.x + dep.width / 2, 0) / endDependencies.length;
                endNode.x = avgX - endNode.width / 2;
            } else {
                endNode.x = (firstLevelWidth - endNode.width) / 2;
            }
            endNode.y = levelY + (levelHeight - endNode.height) / 2;
        }
    }

    // Third pass: Resolve overlaps within each level
    for (const level of sortedLevels) {
        const nodesAtLevel = levelMap.get(level)!;
        if (nodesAtLevel.length <= 1) continue;

        // Sort by x position
        nodesAtLevel.sort((a, b) => a.x - b.x);

        // Check for overlaps and adjust
        for (let i = 1; i < nodesAtLevel.length; i++) {
            const prev = nodesAtLevel[i - 1];
            const curr = nodesAtLevel[i];
            const minGap = SPACING.HORIZONTAL;
            const overlap = prev.x + prev.width + minGap - curr.x;

            if (overlap > 0) {
                // Push current node to the right
                curr.x += overlap;
            }
        }
    }

    // Normalize positions (ensure no negative x values)
    let minX = Infinity;
    for (const node of nodes) {
        minX = Math.min(minX, node.x);
    }
    if (minX < 0) {
        for (const node of nodes) {
            node.x -= minX;
        }
    }

    // Fourth pass: Center each level horizontally
    // Find the total width of the layout (widest level)
    let maxLayoutWidth = 0;
    for (const level of sortedLevels) {
        const nodesAtLevel = levelMap.get(level)!;
        if (nodesAtLevel.length === 0) continue;

        const levelMinX = Math.min(...nodesAtLevel.map(n => n.x));
        const levelMaxX = Math.max(...nodesAtLevel.map(n => n.x + n.width));
        const levelWidth = levelMaxX - levelMinX;
        maxLayoutWidth = Math.max(maxLayoutWidth, levelWidth);
    }

    // Center each level relative to the widest level
    for (const level of sortedLevels) {
        const nodesAtLevel = levelMap.get(level)!;
        if (nodesAtLevel.length === 0) continue;

        const levelMinX = Math.min(...nodesAtLevel.map(n => n.x));
        const levelMaxX = Math.max(...nodesAtLevel.map(n => n.x + n.width));
        const levelWidth = levelMaxX - levelMinX;
        const levelCenterX = levelMinX + levelWidth / 2;
        const targetCenterX = maxLayoutWidth / 2;
        const shiftX = targetCenterX - levelCenterX;

        // Shift all nodes at this level to center them
        for (const node of nodesAtLevel) {
            node.x += shiftX;
        }
    }

    // Final normalization to ensure no negative x values after centering
    minX = Infinity;
    for (const node of nodes) {
        minX = Math.min(minX, node.x);
    }
    if (minX < 0) {
        for (const node of nodes) {
            node.x -= minX;
        }
    }

    return nodes;
}

/**
 * Insert condition pill nodes for switch branches
 * Creates small pill nodes between switch nodes and their target nodes
 */
function insertConditionPills(nodes: LayoutNode[], nodeMap: Map<string, ProcessedNode>): LayoutNode[] {
    const result = [...nodes];
    const nodeById = new Map<string, LayoutNode>();

    // Build lookup map
    for (const node of nodes) {
        nodeById.set(node.id, node);
    }

    // Find switch nodes and create condition pills
    const switchNodes = nodes.filter(n => n.type === "switch");

    for (const switchNode of switchNodes) {
        const procNode = nodeMap.get(switchNode.id);
        if (!procNode) continue;

        const config = procNode.config;
        const cases = config.cases || [];
        const hasDefault = !!config.default;

        // Collect all case targets with their labels
        const caseTargets: Array<{
            targetId: string;
            label: string;
            isDefault: boolean;
            condition: string;
            caseNumber: number;
        }> = [];

        // Add cases with actual condition text and case number
        cases.forEach((caseItem, index) => {
            caseTargets.push({
                targetId: caseItem.node,
                label: caseItem.condition,
                isDefault: false,
                condition: caseItem.condition,
                caseNumber: index + 1,
            });
        });

        // Add default case
        if (hasDefault && config.default) {
            caseTargets.push({
                targetId: config.default,
                label: "default",
                isDefault: true,
                condition: "default",
                caseNumber: cases.length + 1,
            });
        }

        // Create condition pill for each case
        for (const caseTarget of caseTargets) {
            const targetNode = nodeById.get(caseTarget.targetId);
            if (!targetNode) continue;

            // Calculate pill width based on label length (min 60, max 200)
            const estimatedCharWidth = 7; // approximate pixels per character
            const padding = 16; // horizontal padding (reduced)
            const calculatedWidth = Math.min(200, Math.max(60, caseTarget.label.length * estimatedCharWidth + padding));
            const pillWidth = calculatedWidth;
            const pillHeight = NODE_HEIGHTS.CONDITION_PILL;

            // Position pill closer to the target node (with small gap above target)
            const pillGapAboveTarget = 12; // Small gap between pill and target
            const pillY = targetNode.y - pillHeight - pillGapAboveTarget;
            const pillX = targetNode.x + targetNode.width / 2 - pillWidth / 2;

            const conditionPill: LayoutNode = {
                id: `__condition_${switchNode.id}_${caseTarget.targetId}__`,
                type: "condition",
                data: {
                    label: caseTarget.label,
                    conditionLabel: caseTarget.label,
                    switchNodeId: switchNode.id,
                    targetNodeId: caseTarget.targetId,
                    isDefaultCase: caseTarget.isDefault,
                    condition: caseTarget.condition,
                    caseNumber: caseTarget.caseNumber,
                },
                x: pillX,
                y: pillY,
                width: pillWidth,
                height: pillHeight,
                children: [],
            };

            result.push(conditionPill);
        }
    }

    return result;
}

/**
 * Find nodes that connect to the end node (leaf nodes)
 */
function findEndNodeDependencies(nodeMap: Map<string, ProcessedNode>, nodeById: Map<string, LayoutNode>): LayoutNode[] {
    const leafNodes: LayoutNode[] = [];

    for (const procNode of nodeMap.values()) {
        if (procNode.isContainerChild) continue;

        // A node connects to end if it has no dependents (or all dependents are container children)
        const hasNonContainerDependents = procNode.dependents.some(depId => {
            const dep = nodeMap.get(depId);
            return dep && !dep.isContainerChild;
        });

        if (!hasNonContainerDependents) {
            const layoutNode = nodeById.get(procNode.id);
            if (layoutNode) {
                leafNodes.push(layoutNode);
            }
        }
    }

    return leafNodes;
}

/**
 * Position children within a container node
 */
function positionContainerChildren(container: LayoutNode): void {
    const padding = SPACING.CONTAINER_PADDING;
    let childX = padding;
    const childY = NODE_HEIGHTS.CONTAINER_HEADER + padding;

    for (const child of container.children) {
        child.x = childX;
        child.y = childY;
        childX += child.width + SPACING.HORIZONTAL;

        // Recursively position nested children
        if (child.children.length > 0) {
            positionContainerChildren(child);
        }
    }
}

/**
 * Generate edges between nodes
 */
function generateEdges(nodes: LayoutNode[], nodeMap: Map<string, ProcessedNode>): Edge[] {
    const edges: Edge[] = [];
    const nodePositions = new Map<string, LayoutNode>();

    // Build position map
    const buildPositionMap = (nodeList: LayoutNode[]): void => {
        for (const node of nodeList) {
            nodePositions.set(node.id, node);
            if (node.children.length > 0) {
                buildPositionMap(node.children);
            }
        }
    };
    buildPositionMap(nodes);

    const startNode = nodePositions.get("__start__");
    const endNode = nodePositions.get("__end__");

    // Build a map of switch -> target connections that have condition pills
    const switchToTargetPills = new Map<string, Map<string, LayoutNode>>();
    for (const node of nodes) {
        if (node.type === "condition" && node.data.switchNodeId && node.data.targetNodeId) {
            const switchId = node.data.switchNodeId;
            const targetId = node.data.targetNodeId;
            if (!switchToTargetPills.has(switchId)) {
                switchToTargetPills.set(switchId, new Map());
            }
            switchToTargetPills.get(switchId)!.set(targetId, node);
        }
    }

    // Connect start to root nodes
    for (const procNode of nodeMap.values()) {
        if (procNode.dependsOn.length === 0 && !procNode.isContainerChild) {
            const targetNode = nodePositions.get(procNode.id);
            if (startNode && targetNode) {
                edges.push(createEdge("__start__", procNode.id, startNode, targetNode));
            }
        }
    }

    // Track edges we've already created to avoid duplicates
    const createdEdges = new Set<string>();

    // Connect nodes based on dependencies
    for (const procNode of nodeMap.values()) {
        // Skip container children - their dependents have been copied to the container
        if (procNode.isContainerChild) continue;

        const sourceNode = nodePositions.get(procNode.id);
        if (!sourceNode) continue;

        // If no dependents, connect to end
        if (procNode.dependents.length === 0) {
            const edgeKey = `${procNode.id}->__end__`;
            if (!createdEdges.has(edgeKey) && endNode) {
                edges.push(createEdge(procNode.id, "__end__", sourceNode, endNode));
                createdEdges.add(edgeKey);
            }
        }

        // Connect to dependents
        for (const depId of procNode.dependents) {
            const targetNode = nodePositions.get(depId);
            if (!targetNode) continue;

            // Skip if edge already created
            const edgeKey = `${procNode.id}->${depId}`;
            if (createdEdges.has(edgeKey)) continue;

            // Check if this is a switch -> target connection with a condition pill
            const pillMap = switchToTargetPills.get(procNode.id);
            const conditionPill = pillMap?.get(depId);

            if (conditionPill) {
                // Create switch -> pill edge (curved)
                edges.push(createEdge(procNode.id, conditionPill.id, sourceNode, conditionPill));
                // Create pill -> target edge (straight)
                edges.push(createEdge(conditionPill.id, depId, conditionPill, targetNode, true));
            } else {
                // Regular edge
                edges.push(createEdge(procNode.id, depId, sourceNode, targetNode));
            }
            createdEdges.add(edgeKey);
        }
    }

    return edges;
}

/**
 * Create an edge between two positioned nodes
 */
function createEdge(sourceId: string, targetId: string, source: LayoutNode, target: LayoutNode, isStraight: boolean = false): Edge {
    return {
        id: `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        sourceX: source.x + source.width / 2,
        sourceY: source.y + source.height,
        targetX: target.x + target.width / 2,
        targetY: target.y,
        isStraight,
    };
}

/**
 * Calculate total dimensions of the layout
 */
function calculateDimensions(nodes: LayoutNode[]): { totalWidth: number; totalHeight: number } {
    if (nodes.length === 0) {
        return { totalWidth: 0, totalHeight: 0 };
    }

    let maxX = 0;
    let maxY = 0;

    const traverse = (nodeList: LayoutNode[]): void => {
        for (const node of nodeList) {
            maxX = Math.max(maxX, node.x + node.width);
            maxY = Math.max(maxY, node.y + node.height);
            if (node.children.length > 0) {
                traverse(node.children);
            }
        }
    };

    traverse(nodes);

    return {
        totalWidth: maxX + SPACING.CONTAINER_PADDING,
        totalHeight: maxY + SPACING.CONTAINER_PADDING,
    };
}
