/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { PromptsCommand } from "@/lib/components/chat/PromptsCommand";
import type { PromptGroup } from "@/lib/types";

expect.extend(matchers);

// PromptsCommand uses api.webui.get which calls fetchJsonWithError -> fetch -> response.text()
const mockFetch = vi.fn();
function makeFetchResponse(data: unknown) {
    return { ok: true, status: 200, text: async () => JSON.stringify(data) };
}

beforeEach(() => {
    mockFetch.mockResolvedValue(makeFetchResponse([]));
    vi.stubGlobal("fetch", mockFetch);
    // jsdom does not implement scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

const mockGroup: PromptGroup = {
    id: "g1",
    name: "My Prompt",
    description: "A helpful prompt",
    command: "foo",
    userId: "u1",
    isShared: false,
    isPinned: false,
    createdAt: 0,
    updatedAt: 0,
    productionPrompt: {
        id: "p1",
        promptText: "Hello world",
        groupId: "g1",
        userId: "u1",
        version: 1,
        createdAt: 0,
        updatedAt: 0,
    },
};

function renderPrompts(props: Partial<React.ComponentProps<typeof PromptsCommand>> = {}) {
    const textAreaRef = React.createRef<HTMLDivElement>();
    return render(
        <MemoryRouter>
            <PromptsCommand
                isOpen={true}
                onClose={vi.fn()}
                onPromptSelect={vi.fn()}
                textAreaRef={textAreaRef}
                {...props}
            />
        </MemoryRouter>
    );
}

describe("PromptsCommand", () => {
    test("renders nothing when isOpen is false", () => {
        renderPrompts({ isOpen: false });
        expect(screen.queryByTestId("promptCommand")).not.toBeInTheDocument();
    });

    test("renders the prompt list when fetch returns groups", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse([mockGroup]));
        renderPrompts();
        await screen.findByText("My Prompt");
        expect(screen.getByText("/foo")).toBeInTheDocument();
    });

    test("shows 'Create Template from Session' when user messages exist", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse([]));
        renderPrompts({
            messages: [
                {
                    isUser: true,
                    isStatusBubble: false,
                    parts: [{ kind: "text", text: "Hello" }],
                },
            ],
        });
        await screen.findByText("Create Template from Session");
    });

    test("pressing Enter selects the first prompt and calls onPromptSelect", async () => {
        mockFetch.mockResolvedValue(makeFetchResponse([mockGroup]));
        const onPromptSelect = vi.fn();
        renderPrompts({ onPromptSelect });
        await screen.findByText("My Prompt");
        const input = screen.getByPlaceholderText("Search by shortcut or name...");
        fireEvent.keyDown(input, { key: "Enter" });
        expect(onPromptSelect).toHaveBeenCalledWith("Hello world");
    });

    test("clicking the backdrop calls onClose", async () => {
        const onClose = vi.fn();
        renderPrompts({ onClose });
        // Wait for the component to finish rendering (backdrop appears with the popup)
        await screen.findByTestId("promptCommand");
        const backdrop = document.querySelector('[role="presentation"]')!;
        fireEvent.click(backdrop);
        expect(onClose).toHaveBeenCalled();
    });
});