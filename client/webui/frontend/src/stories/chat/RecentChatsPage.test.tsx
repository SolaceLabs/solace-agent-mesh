/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

// Surface the current URL search so tests can assert ?tab=shared is written.
function LocationProbe() {
    const loc = useLocation();
    return <div data-testid="location-search">{loc.search}</div>;
}

const mockListSharedWithMe = vi.fn();
let newNav = true;
let chatSharing = true;
let schedulerEnabled = false;

async function loadPage() {
    vi.resetModules();

    // Stub the session data + mutation hooks.
    vi.doMock("@/lib/api/sessions", async () => {
        const actual = await vi.importActual<typeof import("@/lib/api/sessions")>("@/lib/api/sessions");
        return {
            ...actual,
            useInfiniteSessions: () => ({
                data: { pages: [{ data: [] }] },
                fetchNextPage: vi.fn(),
                hasNextPage: false,
                isFetchingNextPage: false,
            }),
            useRenameSessionWithAI: () => ({ mutate: vi.fn(), isPending: false }),
        };
    });

    // Stub the share hook at the module boundary so we don't need ConfigContext
    // plumbing just to switch the sharing feature flag on/off.
    vi.doMock("@/lib/api/share", () => ({
        useSharedWithMe: () => ({ data: mockListSharedWithMe(), isLoading: false }),
    }));

    // Stub the chat + config hooks directly so tests can toggle the flags they need.
    vi.doMock("@/lib/hooks", async () => {
        const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
        return {
            ...actual,
            useChatContext: () => ({
                sessionId: "sid",
                handleSwitchSession: vi.fn(),
                handleNewSession: vi.fn(),
                updateSessionName: vi.fn(),
                openSessionDeleteModal: vi.fn(),
                closeSessionDeleteModal: vi.fn(),
                confirmSessionDelete: vi.fn(),
                sessionToDelete: null,
                addNotification: vi.fn(),
                currentTaskId: null,
            }),
            useConfigContext: () => ({
                persistenceEnabled: true,
                configFeatureEnablement: { newNavigation: newNav, scheduler: schedulerEnabled, chatSharing },
            }),
            useIsAutoTitleGenerationEnabled: () => false,
            useTitleGeneration: () => ({ generateTitle: vi.fn() }),
            useTitleAnimation: (name: string) => ({ text: name, isAnimating: false, isGenerating: false }),
            useIsChatSharingEnabled: () => chatSharing,
        };
    });

    const mod = await import("@/lib/components/pages/RecentChatsPage");
    return mod.RecentChatsPage;
}

interface RenderOptions {
    chatSharingEnabled?: boolean;
    initialUrl?: string;
}

async function renderPage({ chatSharingEnabled = true, initialUrl = "/recent-chats" }: RenderOptions = {}) {
    chatSharing = chatSharingEnabled;
    newNav = true;
    schedulerEnabled = false;
    const Page = await loadPage();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={[initialUrl]}>
                <Routes>
                    <Route
                        path="/recent-chats"
                        element={
                            <>
                                <Page />
                                <LocationProbe />
                            </>
                        }
                    />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>
    );
}

describe("RecentChatsPage — Shared with Me tab", () => {
    beforeEach(() => {
        mockListSharedWithMe.mockReset();
        mockListSharedWithMe.mockReturnValue([]);
    });

    test("does not show 'Shared with Me' tab when chatSharing flag is off", async () => {
        await renderPage({ chatSharingEnabled: false });
        await screen.findByText("Recent Chats");
        expect(screen.queryByRole("tab", { name: /^shared$/i })).not.toBeInTheDocument();
    });

    test("shows 'Shared with Me' tab when chatSharing flag is on", async () => {
        await renderPage({ chatSharingEnabled: true });
        expect(await screen.findByRole("tab", { name: /^shared$/i })).toBeInTheDocument();
    });

    test("pre-selects 'shared' tab when URL has ?tab=shared", async () => {
        mockListSharedWithMe.mockReturnValue([
            {
                shareId: "s1",
                title: "Alpha Shared Chat",
                ownerEmail: "owner@example.com",
                accessLevel: "RESOURCE_VIEWER",
                sharedAt: Date.now(),
                shareUrl: "https://example.com/shared/s1",
            },
        ]);
        await renderPage({ initialUrl: "/recent-chats?tab=shared" });
        expect(await screen.findByText("Alpha Shared Chat")).toBeInTheDocument();
    });

    test("renders empty state when shared tab is active and no shared items exist", async () => {
        await renderPage({ initialUrl: "/recent-chats?tab=shared" });
        expect(await screen.findByText("No shared chats")).toBeInTheDocument();
    });

    test("clicking the shared tab writes ?tab=shared to the URL", async () => {
        const user = userEvent.setup();
        await renderPage();

        const tab = await screen.findByRole("tab", { name: /^shared$/i });
        await user.click(tab);

        await waitFor(() => {
            expect(screen.getByTestId("location-search").textContent).toBe("?tab=shared");
        });
    });

    test("ignores ?tab=shared when sharing flag is off (falls back to chat tab)", async () => {
        await renderPage({ chatSharingEnabled: false, initialUrl: "/recent-chats?tab=shared" });

        await screen.findByText("Recent Chats");
        expect(screen.queryByRole("tab", { name: /^shared$/i })).not.toBeInTheDocument();
        expect(screen.queryByText("No shared chats")).not.toBeInTheDocument();
    });
});
