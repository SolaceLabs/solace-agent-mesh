import type { AgentCardInfo } from "@/lib/types";

// Workflow config for CompleteOrderWorkflow
export const completeOrderWorkflowConfig = {
    description: "A comprehensive order processing workflow",
    input_schema: {
        type: "object",
        properties: {
            order_id: { type: "string", description: "Unique order identifier" },
            customer_id: { type: "string", description: "Customer identifier" },
            items: {
                type: "array",
                description: "Order items",
                items: {
                    type: "object",
                    properties: {
                        product_id: { type: "string" },
                        quantity: { type: "number" },
                    },
                },
            },
            shipping_priority: { type: "string", enum: ["express", "standard", "economy"] },
        },
        required: ["order_id", "customer_id"],
    },
    output_schema: {
        type: "object",
        properties: {
            order_id: { type: "string", description: "Order identifier" },
            status: { type: "string", description: "Order processing status" },
            customer_name: { type: "string", description: "Customer name" },
            final_total: { type: "number", description: "Final order total" },
            shipping_method: { type: "string", description: "Selected shipping method" },
        },
    },
    output_mapping: {
        order_id: "{{workflow.input.order_id}}",
        status: "{{finalize_order.output.status}}",
        customer_name: "{{enrich_customer.output.name}}",
        final_total: "{{calculate_price.output.final_total}}",
        shipping_method: "{{workflow.input.shipping_priority}}",
    },
    nodes: [
        { id: "validate_order", type: "agent" as const, agent_name: "validate_order" },
        { id: "enrich_customer", type: "agent" as const, agent_name: "enrich_customer" },
        { id: "calculate_price", type: "agent" as const, agent_name: "calculate_price" },
        { id: "check_inventory", type: "agent" as const, agent_name: "check_inventory" },
        { id: "process_shipping", type: "agent" as const, agent_name: "process_shipping" },
        { id: "finalize_order", type: "agent" as const, agent_name: "finalize_order" },
    ],
};

export const completeOrderWorkflow: AgentCardInfo = {
    name: "CompleteOrderWorkflow",
    displayName: "Complete Order Workflow",
    version: "1.0.0",
    description:
        "A comprehensive order processing workflow that validates orders, enriches customer data, calculates pricing with discounts, checks inventory availability, processes shipping, and finalizes orders.\n\nThis workflow demonstrates multiple agent coordination patterns including:\n- Conditional routing based on order value\n- Parallel processing with maps for order items\n- Retry loops for external service calls\n- Sequential agent orchestration",
    isWorkflow: true,
    capabilities: {
        extensions: [
            {
                uri: "https://solace.com/a2a/extensions/sam/workflow-visualization",
                params: {
                    workflow_config: {
                        description: "A comprehensive order processing workflow",
                        input_schema: {
                            type: "object",
                            properties: {
                                order_id: { type: "string", description: "Unique order identifier" },
                                customer_id: { type: "string", description: "Customer identifier" },
                            },
                        },
                        output_schema: {
                            type: "object",
                            properties: {
                                order_status: { type: "string" },
                                final_total: { type: "number" },
                            },
                        },
                        output_mapping: {
                            order_status: "{{finalize_order.output.status}}",
                            final_total: "{{calculate_price.output.total}}",
                        },
                        nodes: [
                            { id: "validate_order", type: "agent", agent_name: "validate_order" },
                            { id: "enrich_customer", type: "agent", agent_name: "enrich_customer" },
                            { id: "calculate_price", type: "agent", agent_name: "calculate_price" },
                            { id: "check_inventory", type: "agent", agent_name: "check_inventory" },
                            { id: "process_shipping", type: "agent", agent_name: "process_shipping" },
                            { id: "finalize_order", type: "agent", agent_name: "finalize_order" },
                        ],
                    },
                },
            },
        ],
    },
    defaultInputModes: [],
    defaultOutputModes: [],
    protocolVersion: "1.0",
    provider: { organization: "solace", url: "" },
    url: "",
    skills: [],
};

export const simpleLoopWorkflow: AgentCardInfo = {
    name: "SimpleLoopWorkflow",
    displayName: "SimpleLoopWorkflow",
    version: "1.0.0",
    description: "A simple workflow demonstrating loop functionality",
    isWorkflow: true,
    capabilities: {},
    defaultInputModes: [],
    defaultOutputModes: [],
    protocolVersion: "1.0",
    provider: { organization: "solace", url: "" },
    url: "",
    skills: [],
};

export const customerEnrichmentWorkflow: AgentCardInfo = {
    name: "CustomerEnrichmentWorkflow",
    displayName: "Customer Enrichment",
    version: "2.1.0",
    description: "Enriches customer data with external sources",
    isWorkflow: true,
    capabilities: {},
    defaultInputModes: [],
    defaultOutputModes: [],
    protocolVersion: "1.0",
    provider: { organization: "solace", url: "" },
    url: "",
    skills: [],
};

export const mockWorkflows: AgentCardInfo[] = [completeOrderWorkflow, simpleLoopWorkflow, customerEnrichmentWorkflow];
