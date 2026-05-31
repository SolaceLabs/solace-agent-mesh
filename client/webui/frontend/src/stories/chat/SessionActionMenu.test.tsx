/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { SessionActionMenu } from "@/lib/components/chat/SessionActionMenu";
import { StoryProvider } from "../mocks/StoryProvider";
import type { Session } from "@/lib/types";

expect.extend(matchers);

const session: Session = {
    id: "s1",
    createdTime: "2024-01-01T00:00:00Z",
    updatedTime: "2024-01-01T00:00:00Z",
    name: "Session One",
    projectId: "p1",
    projectName: "Project One",
};

const renderMenu = (agentMode: boolean) =>
    render(
        <StoryProvider configContextValues={{ agentMode }}>
            <SessionActionMenu
                session={session}
                onRename={vi.fn()}
                onRenameWithAI={vi.fn()}
                onMove={vi.fn()}
                onDelete={vi.fn()}
                onGoToProject={vi.fn()}
                onShare={vi.fn()}
            />
        </StoryProvider>
    );

describe("SessionActionMenu Agent Mode", () => {
    test("shows only Rename, Rename with AI, and Delete in Agent Mode", async () => {
        const user = userEvent.setup();
        renderMenu(true);

        await user.click(screen.getByRole("button"));

        expect(await screen.findByText("Rename")).toBeInTheDocument();
        expect(screen.getByText("Rename with AI")).toBeInTheDocument();
        expect(screen.getByText("Delete")).toBeInTheDocument();

        expect(screen.queryByText("Move to Project")).not.toBeInTheDocument();
        expect(screen.queryByText("Go to Project")).not.toBeInTheDocument();
        expect(screen.queryByText("Share")).not.toBeInTheDocument();
    });

    test("shows project and share actions in Full UI", async () => {
        const user = userEvent.setup();
        renderMenu(false);

        await user.click(screen.getByRole("button"));

        expect(await screen.findByText("Move to Project")).toBeInTheDocument();
        expect(screen.getByText("Go to Project")).toBeInTheDocument();
        expect(screen.getByText("Share")).toBeInTheDocument();
    });
});
