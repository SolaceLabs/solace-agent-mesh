import React from "react";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";

export interface ToolSlot {
    id: string; // The ID of the tool node this slot connects to
    yOffset: number; // The vertical position relative to the agent node top (in pixels)
}

export interface GenericNodeData extends Record<string, unknown> {
    label: string;
    description?: string;
    icon?: string;
    subflow?: boolean;
    isInitial?: boolean;
    isFinal?: boolean;
    variant?: "default" | "pill";
    toolSlots?: ToolSlot[];
    isSkipped?: boolean;
}

const GenericAgentNode: React.FC<NodeProps<Node<GenericNodeData>>> = ({ data }) => {
    const opacityClass = data.isSkipped ? "opacity-50" : "";
    const borderStyleClass = data.isSkipped ? "border-dashed" : "border-solid";

    if (data.variant === "pill") {
        return (
            <div
                className={`cursor-pointer rounded-full border-2 border-indigo-500 bg-indigo-50 px-4 py-2 text-indigo-900 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md dark:border-indigo-400 dark:bg-indigo-900/50 dark:text-indigo-100 ${opacityClass} ${borderStyleClass}`}
                style={{ minWidth: "80px", textAlign: "center" }}
                title={data.description}
            >
                <Handle type="target" position={Position.Top} id="peer-top-input" className="!bg-indigo-500" isConnectable={true} />
                {data.label === "Finish" ? (
                    <Handle type="source" position={Position.Left} id="peer-left-output" className="!bg-indigo-500" isConnectable={true} style={{ top: "45%" }} />
                ) : (
                    <Handle type="target" position={Position.Left} id="peer-left-input" className="!bg-indigo-500" isConnectable={true} style={{ top: "45%" }} />
                )}
                <Handle type="source" position={Position.Bottom} id="peer-bottom-output" className="!bg-indigo-500" isConnectable={true} style={{ bottom: "-2px" }} />
                <div className="flex items-center justify-center">
                    <div className="text-sm font-bold">{data.label}</div>
                </div>
            </div>
        );
    }

    return (
        <div
            className={`cursor-pointer rounded-md border-2 border-blue-700 bg-white px-5 py-3 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-blue-600 dark:bg-gray-800 dark:text-gray-200 ${opacityClass} ${borderStyleClass}`}
            style={{ minWidth: "180px", textAlign: "center", height: "100%" }}
            title={data.description}
        >
            <Handle type="target" position={Position.Top} id="peer-top-input" className="!bg-blue-700" isConnectable={true} />
            <Handle type="source" position={Position.Bottom} id="peer-bottom-output" className="!bg-blue-700" isConnectable={true} />
            <Handle type="target" position={Position.Left} id="peer-left-input" className="!bg-blue-700" isConnectable={true} style={{ top: "25%" }} />
            <Handle type="source" position={Position.Left} id="peer-left-output" className="!bg-blue-700" isConnectable={true} style={{ top: "75%" }} />

            {/* Dynamic Tool Slots */}
            {data.toolSlots &&
                data.toolSlots.map(slot => (
                    <React.Fragment key={slot.id}>
                        {/* Output handle (Request) - positioned slightly higher */}
                        <Handle
                            type="source"
                            position={Position.Right}
                            id={`agent-out-${slot.id}`}
                            className="!bg-blue-700"
                            style={{ top: `${slot.yOffset - 12}px`, right: "-2px" }}
                            isConnectable={true}
                        />
                        {/* Input handle (Response) - positioned slightly lower */}
                        <Handle
                            type="target"
                            position={Position.Right}
                            id={`agent-in-${slot.id}`}
                            className="!bg-blue-700"
                            style={{ top: `${slot.yOffset + 12}px`, right: "-2px" }}
                            isConnectable={true}
                        />
                    </React.Fragment>
                ))}

            <div className="flex items-center justify-center">
                <div className="text-md truncate font-semibold" style={{ maxWidth: "200px" }}>
                    {data.label}
                </div>
            </div>
        </div>
    );
};

export default GenericAgentNode;
