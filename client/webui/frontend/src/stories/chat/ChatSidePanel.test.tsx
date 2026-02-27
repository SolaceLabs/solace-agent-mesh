/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ChatSidePanel } from "@/lib/components/chat/ChatSidePanel";
import { StoryProvider } from "../mocks/StoryProvider";
import { documentSearchRagData } from "../mocks/citations";

expect.extend(matchers);

describe("ChatSidePanel document sources", () => {
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

    test("shows DocumentSourcesPanel when document search results are present", async () => {
        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={chatContextWithRagData} taskContextValues={taskContext}>
                    <ChatSidePanel onCollapsedToggle={vi.fn()} isSidePanelCollapsed={false} setIsSidePanelCollapsed={vi.fn()} isSidePanelTransitioning={false} />
                </StoryProvider>
            </MemoryRouter>
        );

        expect(await screen.findByText(/3 Documents/)).toBeInTheDocument();
        expect(await screen.findByText(/6 Citations/)).toBeInTheDocument();

        expect(screen.queryByText(/6 Sources/)).not.toBeInTheDocument();
    });
});
