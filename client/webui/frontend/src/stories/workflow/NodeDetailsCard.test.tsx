/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { NodeDetails } from "@/lib/components/activities/FlowChart/utils/nodeDetailsHelper";
import type { VisualizerStep } from "@/lib/types";

expect.extend(matchers);

async function loadCard() {
    vi.resetModules();

    vi.doMock("@/lib/hooks", () => ({
        useChatContext: () => ({
            artifacts: [],
            setPreviewArtifact: vi.fn(),
            setActiveSidePanelTab: vi.fn(),
            setIsSidePanelCollapsed: vi.fn(),
            navigateArtifactVersion: vi.fn(),
            sessionId: "test-session",
        }),
    }));

    const mod = await import("@/lib/components/activities/FlowChart/NodeDetailsCard");
    return mod.default;
}

function toolInvocationDetails(toolArguments: Record<string, unknown> | null | undefined): NodeDetails {
    const step: VisualizerStep = {
        id: "step-1",
        type: "AGENT_TOOL_INVOCATION_START",
        timestamp: new Date().toISOString(),
        title: "Tool Invocation",
        data: {
            toolInvocationStart: {
                functionCallId: "fc-1",
                toolName: "search",
                toolArguments: toolArguments as Record<string, unknown>,
            },
        },
        rawEventIds: [],
        nestingLevel: 0,
        owningTaskId: "task-1",
    };
    return {
        nodeType: "tool",
        label: "search",
        requestStep: step,
    };
}

describe("NodeDetailsCard — tool-argument null guards", () => {
    let NodeDetailsCard: React.ComponentType<{ nodeDetails: NodeDetails }>;

    beforeEach(async () => {
        NodeDetailsCard = await loadCard();
    });

    test("renders 'No arguments' when toolArguments is null (renderFormattedArguments guard)", () => {
        render(<NodeDetailsCard nodeDetails={toolInvocationDetails(null)} />);
        expect(screen.getByText("No arguments")).toBeInTheDocument();
    });

    test("renders 'No arguments' when toolArguments is undefined", () => {
        render(<NodeDetailsCard nodeDetails={toolInvocationDetails(undefined)} />);
        expect(screen.getByText("No arguments")).toBeInTheDocument();
    });

    test("handles toolArguments containing a null nested object (renderArgumentValue guard)", () => {
        // The nested { inner: null } value reaches the typeof==="object" branch
        // at renderArgumentValue; the null-guard short-circuits Object.entries.
        render(<NodeDetailsCard nodeDetails={toolInvocationDetails({ wrapper: null })} />);
        expect(screen.getByText("wrapper")).toBeInTheDocument();
    });
});
