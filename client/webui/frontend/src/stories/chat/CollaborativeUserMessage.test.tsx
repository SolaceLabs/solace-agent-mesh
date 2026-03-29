/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { CollaborativeUserMessage } from "@/lib/components/chat/CollaborativeUserMessage";
import { StoryProvider } from "../mocks/StoryProvider";
import type { MessageFE } from "@/lib/types";

expect.extend(matchers);

// Mock MessageHoverButtons to avoid pulling in complex dependencies
vi.mock("@/lib/components/chat/MessageHoverButtons", () => ({
    MessageHoverButtons: () => <div data-testid="hover-buttons" />,
}));

function makeMessage(text: string): MessageFE {
    return {
        isUser: true,
        role: "user",
        parts: [{ kind: "text" as const, text }],
    } as MessageFE;
}

function renderMessage(text: string, userName: string) {
    return render(
        <MemoryRouter>
            <StoryProvider>
                <CollaborativeUserMessage message={makeMessage(text)} userName={userName} timestamp={1700000000000} />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("CollaborativeUserMessage", () => {
    test("renders user name attribution", () => {
        renderMessage("Hello", "Alice");
        // The MessageAttribution component renders the user name
        expect(screen.getByText("Alice")).toBeInTheDocument();
    });

    test("renders message text content", () => {
        renderMessage("Can you help me with this?", "Bob");
        expect(screen.getByText("Can you help me with this?")).toBeInTheDocument();
    });

    test("renders empty content when message has no text part", () => {
        const message = {
            isUser: true,
            role: "user",
            parts: [],
        } as unknown as MessageFE;

        render(
            <MemoryRouter>
                <StoryProvider>
                    <CollaborativeUserMessage message={message} userName="Charlie" timestamp={1700000000000} />
                </StoryProvider>
            </MemoryRouter>
        );

        // User name should still be shown even with empty message
        expect(screen.getByText("Charlie")).toBeInTheDocument();
    });
});
