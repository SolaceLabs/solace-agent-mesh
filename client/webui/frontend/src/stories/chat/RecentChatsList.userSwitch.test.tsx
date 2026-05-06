/// <reference types="@testing-library/jest-dom" />
/**
 * Test for the recentNotReady spinner gate in RecentChatsList. When the auth
 * user changes, useRecentSessions reads under a new (user-scoped) cache key
 * so its data is briefly `undefined` while the fresh fetch is in-flight. The
 * gate must keep the prior user's titles off-screen during that window.
 */
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

expect.extend(matchers);

type RecentResult = {
    data: Array<{ id: string; name: string; updatedTime: string }> | undefined;
    isLoading: boolean;
    isFetching: boolean;
};

let recentResult: RecentResult = { data: undefined, isLoading: true, isFetching: true };

async function loadList() {
    vi.resetModules();

    vi.doMock("@/lib/api/sessions", () => ({
        useRecentSessions: () => recentResult,
        useMarkSessionViewed: () => ({ mutate: vi.fn() }),
    }));

    vi.doMock("@/lib/api/share", () => ({
        useSharedWithMe: () => ({ data: [], isLoading: false }),
    }));

    vi.doMock("@/lib/hooks", async () => {
        const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
        return {
            ...actual,
            useChatContext: () => ({ sessionId: "current", handleSwitchSession: vi.fn(), currentTaskId: null }),
            useConfigContext: () => ({ persistenceEnabled: true, configFeatureEnablement: { chatSharing: false } }),
            useIsAutoTitleGenerationEnabled: () => false,
            useIsChatSharingEnabled: () => false,
            useTitleAnimation: (name: string) => ({ text: name, isAnimating: false, isGenerating: false }),
        };
    });

    const mod = await import("@/lib/components/chat/RecentChatsList");
    return mod.RecentChatsList;
}

async function renderList() {
    const RecentChatsList = await loadList();
    return render(
        <MemoryRouter>
            <RecentChatsList />
        </MemoryRouter>
    );
}

describe("RecentChatsList — recentNotReady spinner gate", () => {
    beforeEach(() => {
        recentResult = { data: undefined, isLoading: true, isFetching: true };
    });

    test("first paint with user A renders user A's titles", async () => {
        recentResult = {
            data: [{ id: "a-1", name: "Alice's Project Plan", updatedTime: new Date().toISOString() }],
            isLoading: false,
            isFetching: false,
        };
        const { container } = await renderList();

        expect(await screen.findByText("Alice's Project Plan")).toBeInTheDocument();
        // Sanity: no spinner visible when data is resolved.
        expect(container.querySelector("[role='status']")).toBeNull();
    });

    test("during user switch (data: undefined, isFetching: true) prior user's titles are NOT visible", async () => {
        // Simulate the in-flight window after auth user changes from A to B:
        // the new userId-scoped key has no cached entry yet, so data===undefined
        // even though isLoading might have already flipped false.
        recentResult = { data: undefined, isLoading: false, isFetching: true };
        await renderList();

        // No previous-user titles should leak through.
        expect(screen.queryByText("Alice's Project Plan")).not.toBeInTheDocument();
        // The empty-state ("No recent chats") must NOT appear either — the
        // gate must show the spinner so we don't briefly imply user B has
        // no chats while their data is still loading.
        expect(screen.queryByText(/no recent chats/i)).not.toBeInTheDocument();
    });

    test("when data resolves for user B, only user B's titles render", async () => {
        recentResult = {
            data: [{ id: "b-1", name: "Bob's Sprint Review", updatedTime: new Date().toISOString() }],
            isLoading: false,
            isFetching: false,
        };
        await renderList();

        expect(await screen.findByText("Bob's Sprint Review")).toBeInTheDocument();
        expect(screen.queryByText("Alice's Project Plan")).not.toBeInTheDocument();
    });
});
