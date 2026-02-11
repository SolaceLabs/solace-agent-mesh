/**
 * Expression Parser Utility
 * Extracts node references from template expressions like {{node_a.output.my_val > 2}}
 */

/**
 * Extracts node IDs referenced in a template expression.
 *
 * Handles patterns like:
 * - {{node_a.output.field}} -> ['node_a']
 * - {{node_a.output.x > node_b.output.y}} -> ['node_a', 'node_b']
 * - {{workflow.input.field}} -> ['__start__'] (maps to start node)
 * - {{some_node.output.val + 5}} -> ['some_node']
 *
 * @param expression - The expression string to parse (e.g., "{{node_a.output.my_val > 2}}")
 * @returns Array of unique node IDs found in the expression
 */
export function extractNodeReferences(expression: string): string[] {
    if (!expression) return [];

    const nodeRefs = new Set<string>();

    // Match content inside {{ }} - handles multiple template blocks in one expression
    const templateRegex = /\{\{([^}]+)\}\}/g;
    let templateMatch;

    while ((templateMatch = templateRegex.exec(expression)) !== null) {
        const content = templateMatch[1];

        // Match identifiers followed by a dot and property access
        // This catches patterns like: node_id.output.xxx, node_id.input.xxx, workflow.input.xxx
        // The regex looks for word characters (identifier) followed by dot and another identifier
        const nodeRefRegex = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*(output|input|[a-zA-Z_][a-zA-Z0-9_]*)/g;
        let refMatch;

        while ((refMatch = nodeRefRegex.exec(content)) !== null) {
            const nodeId = refMatch[1];

            // 'workflow' is a special keyword that refers to workflow-level input
            // Map it to '__start__' node which represents workflow input
            if (nodeId === "workflow") {
                nodeRefs.add("__start__");
            } else {
                nodeRefs.add(nodeId);
            }
        }
    }

    return Array.from(nodeRefs);
}

/**
 * Validates extracted node references against a set of known node IDs.
 * Returns only the references that correspond to actual nodes in the workflow.
 *
 * @param nodeReferences - Array of node IDs extracted from an expression
 * @param knownNodeIds - Set of valid node IDs in the current workflow
 * @returns Array of node IDs that exist in the workflow
 */
export function validateNodeReferences(nodeReferences: string[], knownNodeIds: Set<string>): string[] {
    return nodeReferences.filter(nodeId => knownNodeIds.has(nodeId));
}

/**
 * Convenience function that extracts and validates node references in one step.
 *
 * @param expression - The expression string to parse
 * @param knownNodeIds - Set of valid node IDs in the current workflow
 * @returns Array of valid node IDs referenced in the expression
 */
export function getValidNodeReferences(expression: string, knownNodeIds: Set<string>): string[] {
    const refs = extractNodeReferences(expression);
    return validateNodeReferences(refs, knownNodeIds);
}

/**
 * Extracts all node IDs from a workflow config.
 * Includes the special __start__ and __end__ nodes.
 *
 * @param config - The workflow configuration object
 * @returns Set of all node IDs in the workflow
 */
export function extractNodeIdsFromConfig(config: { nodes?: Array<{ id?: string }> }): Set<string> {
    const ids = new Set<string>();

    // Add special start/end nodes
    ids.add("__start__");
    ids.add("__end__");

    // Add node IDs from config
    if (config.nodes) {
        for (const node of config.nodes) {
            if (node.id) {
                ids.add(node.id);
            }
        }
    }

    return ids;
}
