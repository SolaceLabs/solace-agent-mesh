/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import React from "react";

import { MentionsCommand } from "@/lib/components/chat/MentionsCommand";
import type { Person } from "@/lib/types";

expect.extend(matchers);

// Mock recentMentions util
vi.mock("@/lib/utils/recentMentions", () => ({
    getRecentMentions: vi.fn().mockReturnValue([]),
}));


const mockPerson: Person = {
    id: "person-1",
    displayName: "Alice Smith",
    workEmail: "alice@example.com",
    jobTitle: "Engineer",
};

// MentionsCommand only renders content when popupPosition is set via a useEffect
// that reads window.getSelection(). Stub it before each render.
function stubSelection() {
    const mockRange = { getBoundingClientRect: () => ({ top: 100, bottom: 120, left: 50, right: 200, width: 150, height: 20 }) };
    vi.stubGlobal("getSelection", () => ({ rangeCount: 1, getRangeAt: () => mockRange }));
    vi.stubGlobal("innerWidth", 1200);
    vi.stubGlobal("innerHeight", 800);
}

// Stub fetch to return empty results by default; override per-test for people.
// client.ts calls response.text() then JSON.parse, so we must mock text() not json().
const mockFetch = vi.fn();
function makeFetchResponse(data: unknown) {
    return { ok: true, status: 200, text: async () => JSON.stringify(data) };
}
beforeEach(() => {
    mockFetch.mockResolvedValue(makeFetchResponse({ data: [] }));
    vi.stubGlobal("fetch", mockFetch);
});

function renderMentions(props: Partial<React.ComponentProps<typeof MentionsCommand>> = {}) {
    stubSelection();
    const Wrapper = () => {
        const textAreaRef = React.useRef<HTMLDivElement>(null);
        return (
            <>
                <div ref={textAreaRef} />
                <MentionsCommand
                    onClose={vi.fn()}
                    onPersonSelect={vi.fn()}
                    searchQuery=""
                    isOpen={true}
                    {...props}
                    textAreaRef={textAreaRef}
                />
            </>
        );
    };
    return render(<MemoryRouter><Wrapper /></MemoryRouter>);
}

describe("MentionsCommand", () => {
    test("renders nothing when isOpen is false", () => {
        const { container } = renderMentions({ isOpen: false });
        // When closed, only the anchor div is rendered — no popup content
        expect(screen.queryByText("Recent mentions")).not.toBeInTheDocument();
        expect(container).toBeInTheDocument();
    });

    test("shows 'Recent mentions' header when searchQuery is empty", async () => {
        renderMentions({ searchQuery: "" });
        await screen.findByText("Recent mentions");
    });

    test("shows search header when searchQuery has content", async () => {
        renderMentions({ searchQuery: "alice" });
        await screen.findByText(/Searching for/);
        expect(screen.getByText("alice")).toBeInTheDocument();
    });

    test("shows 'No recent mentions' when recent list is empty and searchQuery is empty", async () => {
        renderMentions({ searchQuery: "" });
        await screen.findByText(/No recent mentions/);
    });

    test("pressing Escape calls onClose", async () => {
        const onClose = vi.fn();
        renderMentions({ onClose });
        await screen.findByText("Recent mentions");
        fireEvent.keyDown(window, { key: "Escape" });
        expect(onClose).toHaveBeenCalled();
    });

    test("backdrop click calls onClose", async () => {
        const onClose = vi.fn();
        renderMentions({ onClose });
        await screen.findByText("Recent mentions");
        const backdrop = document.querySelector('[role="presentation"]')!;
        fireEvent.click(backdrop);
        expect(onClose).toHaveBeenCalled();
    });

    test("renders search results when people are returned from API", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse({ data: [mockPerson] }));
        renderMentions({ searchQuery: "alice" });
        await screen.findByText("Alice Smith");
        expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    test("clicking a person result calls onPersonSelect and onClose", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse({ data: [mockPerson] }));
        const onPersonSelect = vi.fn();
        const onClose = vi.fn();
        renderMentions({ searchQuery: "alice", onPersonSelect, onClose });

        const nameEl = await screen.findByText("Alice Smith");
        fireEvent.click(nameEl.closest("button")!);

        expect(onPersonSelect).toHaveBeenCalledWith(mockPerson);
        expect(onClose).toHaveBeenCalled();
    });

    test("Enter key selects the first person from search results", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse({ data: [mockPerson] }));
        const onPersonSelect = vi.fn();
        renderMentions({ searchQuery: "alice", onPersonSelect });

        await screen.findByText("Alice Smith");
        fireEvent.keyDown(window, { key: "Enter" });
        await waitFor(() => expect(onPersonSelect).toHaveBeenCalledWith(mockPerson));
    });

    test("hovering a search result does not throw (mouseEnter handler)", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse({ data: [mockPerson] }));
        renderMentions({ searchQuery: "alice" });
        const nameEl = await screen.findByText("Alice Smith");
        const btn = nameEl.closest("button")!;
        fireEvent.mouseEnter(btn);
        // No crash and the item is still present
        expect(btn).toBeInTheDocument();
    });
});