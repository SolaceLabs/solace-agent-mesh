/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ChatSidePanel } from "@/lib/components/chat/ChatSidePanel";
import { StoryProvider } from "../mocks/StoryProvider";
import { documentSearchRagData } from "../mocks/citations";

expect.extend(matchers);

describe("projectIndexing feature flag", () => {
    const chatContextWithRagData = {
        activeSidePanelTab: "rag" as const,
        ragData: documentSearchRagData,
        ragEnabled: true,
    };

    const taskContext = {
        isReconnecting: false,
        isTaskMonitorConnecting: false,
        isTaskMonitorConnected: true,
        monitoredTasks: {},
        loadTaskFromBackend: vi.fn().mockResolvedValue(null),
    };

    test("shows RAGInfoPanel when projectIndexing flag is disabled", async () => {
        render(
            <MemoryRouter>
                <StoryProvider
                    chatContextValues={chatContextWithRagData}
                    taskContextValues={taskContext}
                    configContextValues={{
                        configFeatureEnablement: { projectIndexing: false },
                    }}
                >
                    <ChatSidePanel onCollapsedToggle={vi.fn()} isSidePanelCollapsed={false} setIsSidePanelCollapsed={vi.fn()} isSidePanelTransitioning={false} />
                </StoryProvider>
            </MemoryRouter>
        );

        expect(await screen.findByText(/6 Sources/)).toBeInTheDocument();
        expect(screen.queryByText(/3 Documents/)).not.toBeInTheDocument();
    });

    test("shows DocumentSourcesPanel when projectIndexing flag is enabled", async () => {
        render(
            <MemoryRouter>
                <StoryProvider
                    chatContextValues={chatContextWithRagData}
                    taskContextValues={taskContext}
                    configContextValues={{
                        configFeatureEnablement: { projectIndexing: true },
                    }}
                >
                    <ChatSidePanel onCollapsedToggle={vi.fn()} isSidePanelCollapsed={false} setIsSidePanelCollapsed={vi.fn()} isSidePanelTransitioning={false} />
                </StoryProvider>
            </MemoryRouter>
        );

        expect(await screen.findByText(/3 Documents/)).toBeInTheDocument();
        expect(await screen.findByText(/6 Citations/)).toBeInTheDocument();

        expect(screen.queryByText(/6 Sources/)).not.toBeInTheDocument();
    });
});
