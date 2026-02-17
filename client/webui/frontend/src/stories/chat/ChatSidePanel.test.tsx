/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { RAGInfoPanel } from "@/lib/components/chat/rag/RAGInfoPanel";
import { DocumentSourcesPanel } from "@/lib/components/chat/rag/DocumentSourcesPanel";
import { ChatSidePanel } from "@/lib/components/chat/ChatSidePanel";
import { StoryProvider } from "../mocks/StoryProvider";
import { documentSearchRagData } from "../mocks/citations";

expect.extend(matchers);

describe("ChatSidePanel", () => {
    describe("RAGInfoPanel", () => {
        test("shows Activity and Sources tabs when enabled with data", async () => {
            render(
                <MemoryRouter>
                    <RAGInfoPanel ragData={documentSearchRagData} enabled={true} />
                </MemoryRouter>
            );

            // RAGInfoPanel renders tabs for Activity and Sources
            expect(await screen.findByRole("tab", { name: /activity/i })).toBeInTheDocument();
            expect(await screen.findByRole("tab", { name: /sources/i })).toBeInTheDocument();
        });

        test("shows disabled message when not enabled", async () => {
            render(
                <MemoryRouter>
                    <RAGInfoPanel ragData={documentSearchRagData} enabled={false} />
                </MemoryRouter>
            );

            expect(await screen.findByText("RAG Sources")).toBeInTheDocument();
            expect(await screen.findByText("RAG source visibility is disabled in settings")).toBeInTheDocument();
        });
    });

    describe("DocumentSourcesPanel", () => {
        test("shows document count and citations when enabled with data", async () => {
            render(
                <MemoryRouter>
                    <DocumentSourcesPanel ragData={documentSearchRagData} enabled={true} />
                </MemoryRouter>
            );

            // DocumentSourcesPanel shows document and citation counts
            expect(await screen.findByText(/3 Documents/)).toBeInTheDocument();
            expect(await screen.findByText(/6 Citations/)).toBeInTheDocument();
        });

        test("shows disabled message when not enabled", async () => {
            render(
                <MemoryRouter>
                    <DocumentSourcesPanel ragData={documentSearchRagData} enabled={false} />
                </MemoryRouter>
            );

            expect(await screen.findByText("Document Sources")).toBeInTheDocument();
            expect(await screen.findByText("Source visibility is disabled in settings")).toBeInTheDocument();
        });
    });

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

            // RAGInfoPanel shows "6 Sources" in its tab (not "3 Documents")
            expect(await screen.findByText(/6 Sources/)).toBeInTheDocument();
            // DocumentSourcesPanel content should NOT be present
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

            // DocumentSourcesPanel shows document counts (not "6 Sources")
            expect(await screen.findByText(/3 Documents/)).toBeInTheDocument();
            expect(await screen.findByText(/6 Citations/)).toBeInTheDocument();
            // RAGInfoPanel content should NOT be present
            expect(screen.queryByText(/6 Sources/)).not.toBeInTheDocument();
        });
    });
});
