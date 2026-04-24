/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";

expect.extend(matchers);

const handleSwitchSession = vi.fn();

let mockSessions: Array<{ id: string; name: string; updatedTime: string }> = [];
let mockShared: Array<{ shareId: string; title: string; ownerEmail: string; accessLevel: string; sharedAt: number; shareUrl: string; sessionId?: string | null }> = [];
let chatSharing = true;

function LocationProbe() {
    const loc = useLocation();
    return <div data-testid="location-path">{loc.pathname}</div>;
}

async function loadList() {
    vi.resetModules();

    vi.doMock("@/lib/api/sessions", () => ({
        useRecentSessions: () => ({ data: mockSessions, isLoading: false }),
        useMarkSessionViewed: () => ({ mutate: vi.fn() }),
    }));

    vi.doMock("@/lib/api/share", () => ({
        useSharedWithMe: () => ({ data: mockShared, isLoading: false }),
    }));

    vi.doMock("@/lib/hooks", async () => {
        const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
        return {
            ...actual,
            useChatContext: () => ({
                sessionId: "current-session",
                handleSwitchSession,
                currentTaskId: null,
            }),
            useConfigContext: () => ({
                persistenceEnabled: true,
                configFeatureEnablement: { chatSharing },
            }),
            useIsAutoTitleGenerationEnabled: () => false,
            useIsChatSharingEnabled: () => chatSharing,
            useTitleAnimation: (name: string) => ({ text: name, isAnimating: false, isGenerating: false }),
        };
    });

    const mod = await import("@/lib/components/chat/RecentChatsList");
    return mod.RecentChatsList;
}

async function renderList() {
    const RecentChatsList = await loadList();
    return render(
        <MemoryRouter initialEntries={["/start"]}>
            <Routes>
                <Route
                    path="/start"
                    element={
                        <>
                            <RecentChatsList />
                            <LocationProbe />
                        </>
                    }
                />
                <Route path="/chat" element={<LocationProbe />} />
                <Route path="/shared-chat/:shareId" element={<LocationProbe />} />
            </Routes>
        </MemoryRouter>
    );
}

function makeSession(id: string, name: string, iso: string) {
    return { id, name, updatedTime: iso };
}

function makeShared(shareId: string, title: string, sharedAt: number, extra: Partial<{ accessLevel: string; sessionId: string | null }> = {}) {
    return {
        shareId,
        title,
        ownerEmail: "owner@example.com",
        accessLevel: "RESOURCE_VIEWER",
        sharedAt,
        shareUrl: `https://example.com/shared/${shareId}`,
        sessionId: null,
        ...extra,
    };
}

describe("RecentChatsList — merged shared entries", () => {
    beforeEach(() => {
        handleSwitchSession.mockReset();
        mockSessions = [];
        mockShared = [];
        chatSharing = true;
    });

    test("shows 'No recent chats' empty state when both lists are empty", async () => {
        await renderList();
        expect(await screen.findByText(/no recent chats/i)).toBeInTheDocument();
    });

    test("renders shared chat titles alongside recent sessions", async () => {
        mockSessions = [makeSession("s1", "Session One", "2024-01-01T00:00:00Z")];
        mockShared = [makeShared("share-1", "Shared Alpha", Date.now())];
        await renderList();

        expect(await screen.findByText("Shared Alpha")).toBeInTheDocument();
        expect(screen.getByText("Session One")).toBeInTheDocument();
    });

    test("sorts entries by timestamp (most recent first)", async () => {
        const now = Date.now();
        mockSessions = [makeSession("s-old", "Old Session", new Date(now - 10_000_000).toISOString()), makeSession("s-new", "New Session", new Date(now - 1_000).toISOString())];
        mockShared = [makeShared("share-mid", "Mid Shared", now - 5_000)];

        await renderList();

        // Find all button labels in order.
        const buttons = await screen.findAllByRole("button");
        const labels = buttons.map(b => b.textContent?.trim()).filter(Boolean);
        // Expect order: New Session (most recent) → Mid Shared → Old Session
        const newIdx = labels.findIndex(l => l === "New Session");
        const midIdx = labels.findIndex(l => l === "Mid Shared");
        const oldIdx = labels.findIndex(l => l === "Old Session");
        expect(newIdx).toBeLessThan(midIdx);
        expect(midIdx).toBeLessThan(oldIdx);
    });

    test("omits shared items when chatSharing flag is off", async () => {
        chatSharing = false;
        mockSessions = [makeSession("s1", "Session One", "2024-01-01T00:00:00Z")];
        mockShared = [makeShared("share-1", "Shared Alpha", Date.now())];

        await renderList();
        expect(await screen.findByText("Session One")).toBeInTheDocument();
        expect(screen.queryByText("Shared Alpha")).not.toBeInTheDocument();
    });

    test("shared viewer entry navigates to /shared-chat/:shareId", async () => {
        mockShared = [makeShared("share-42", "Viewer Chat", Date.now())];
        const user = userEvent.setup();
        await renderList();

        await user.click(await screen.findByRole("button", { name: /viewer chat/i }));
        expect(await screen.findByText("/shared-chat/share-42", { selector: "[data-testid='location-path']" })).toBeInTheDocument();
    });

    test("shared editor entry (with sessionId) switches to /chat and opens that session", async () => {
        mockShared = [makeShared("share-7", "Editor Chat", Date.now(), { accessLevel: "RESOURCE_EDITOR", sessionId: "sess-7" })];
        const user = userEvent.setup();
        await renderList();

        await user.click(await screen.findByRole("button", { name: /editor chat/i }));
        expect(await screen.findByText("/chat", { selector: "[data-testid='location-path']" })).toBeInTheDocument();
        expect(handleSwitchSession).toHaveBeenCalledWith("sess-7");
    });

    test("respects maxItems cap across combined list", async () => {
        mockSessions = Array.from({ length: 10 }, (_, i) => makeSession(`s${i}`, `Session ${i}`, new Date(Date.now() - i * 1000).toISOString()));
        mockShared = Array.from({ length: 10 }, (_, i) => makeShared(`sh${i}`, `Shared ${i}`, Date.now() - i * 500));
        const RecentChatsList = await loadList();
        render(
            <MemoryRouter>
                <RecentChatsList maxItems={5} />
            </MemoryRouter>
        );

        const buttons = await screen.findAllByRole("button");
        expect(buttons).toHaveLength(5);
    });
});
