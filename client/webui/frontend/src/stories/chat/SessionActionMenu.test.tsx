/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { SessionActionMenu } from "@/lib/components/chat/SessionActionMenu";
import { ChatSurfaceContext, FULL_CHAT_SURFACE, type ChatSurface } from "@/lib/contexts";
import type { Session } from "@/lib/types";

expect.extend(matchers);

const EMBEDDED_SURFACE: ChatSurface = {
    ...FULL_CHAT_SURFACE,
    variant: "embedded",
    sessionActions: ["rename", "renameWithAI", "delete"],
};

const session = { id: "s1", name: "My session", projectId: "p1" } as unknown as Session;

function renderMenu(surface: ChatSurface) {
    const handlers = {
        onRename: vi.fn(),
        onRenameWithAI: vi.fn(),
        onMove: vi.fn(),
        onDelete: vi.fn(),
        onGoToProject: vi.fn(),
        onShare: vi.fn(),
    };
    render(
        <ChatSurfaceContext.Provider value={surface}>
            <SessionActionMenu session={session} {...handlers} />
        </ChatSurfaceContext.Provider>
    );
    return handlers;
}

async function openMenu() {
    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));
}

describe("SessionActionMenu — surface allowlist", () => {
    test("full surface shows every action", async () => {
        renderMenu(FULL_CHAT_SURFACE);
        await openMenu();

        expect(screen.getByText("Go to Project")).toBeInTheDocument();
        expect(screen.getByText("Rename")).toBeInTheDocument();
        expect(screen.getByText("Rename with AI")).toBeInTheDocument();
        expect(screen.getByText("Move to Project")).toBeInTheDocument();
        expect(screen.getByText("Share")).toBeInTheDocument();
        expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    test("embedded surface shows only Rename / Rename with AI / Delete", async () => {
        renderMenu(EMBEDDED_SURFACE);
        await openMenu();

        expect(screen.getByText("Rename")).toBeInTheDocument();
        expect(screen.getByText("Rename with AI")).toBeInTheDocument();
        expect(screen.getByText("Delete")).toBeInTheDocument();

        expect(screen.queryByText("Go to Project")).not.toBeInTheDocument();
        expect(screen.queryByText("Move to Project")).not.toBeInTheDocument();
        expect(screen.queryByText("Share")).not.toBeInTheDocument();
    });
});
