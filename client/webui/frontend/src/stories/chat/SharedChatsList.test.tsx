/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { StoryProvider } from "../mocks/StoryProvider";
import type { SharedWithMeItem } from "@/lib/types/share";
import * as shareService from "@/lib/api/share/service";

expect.extend(matchers);

import { SharedChatsList } from "@/lib/components/chat/SharedChatsList";

function makeSharedItem(overrides: Partial<SharedWithMeItem> = {}): SharedWithMeItem {
    return {
        shareId: "share-1",
        title: "Shared Chat Title",
        ownerEmail: "owner@example.com",
        accessLevel: "RESOURCE_VIEWER",
        sharedAt: Date.now(),
        shareUrl: "https://example.com/shared/share-1",
        ...overrides,
    };
}

function renderList() {
    return render(
        <MemoryRouter>
            <StoryProvider>
                <SharedChatsList />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("SharedChatsList", () => {
    let listSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        listSpy = vi.spyOn(shareService, "listSharedWithMe");
    });

    test("shows 'Shared with Me' header when items exist", async () => {
        listSpy.mockResolvedValue([makeSharedItem()]);
        renderList();
        expect(await screen.findByText("Shared with Me")).toBeInTheDocument();
    });

    test("shows shared chat titles", async () => {
        listSpy.mockResolvedValue([makeSharedItem({ shareId: "s1", title: "Alpha Chat" }), makeSharedItem({ shareId: "s2", title: "Beta Chat" })]);
        renderList();
        expect(await screen.findByText("Alpha Chat")).toBeInTheDocument();
        expect(screen.getByText("Beta Chat")).toBeInTheDocument();
    });

    test("renders nothing when no shared items", async () => {
        listSpy.mockResolvedValue([]);
        const { container } = renderList();

        await waitFor(() => {
            expect(listSpy).toHaveBeenCalled();
        });

        expect(screen.queryByText("Shared with Me")).not.toBeInTheDocument();
        expect(container.textContent).toBe("");
    });
});
