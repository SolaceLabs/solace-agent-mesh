/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ArtifactCard } from "@/lib/components/chat/artifact/ArtifactCard";
import { StoryProvider } from "../mocks/StoryProvider";
import type { ArtifactInfo } from "@/lib/types";

expect.extend(matchers);

const mockArtifact: ArtifactInfo = {
    filename: "report.pdf",
    mime_type: "application/pdf",
    size: 1024,
    last_modified: "2024-01-01T00:00:00.000Z",
    uri: "artifact://report.pdf",
};

function renderCard(props: Partial<React.ComponentProps<typeof ArtifactCard>> = {}, chatContextValues = {}) {
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={chatContextValues}>
                <ArtifactCard artifact={mockArtifact} {...props} />
            </StoryProvider>
        </MemoryRouter>
    );
}

// The outer ArtifactCard wrapper is a div[role="button"]; ArtifactMessage renders
// native <button> elements for actions. Filter to find the card div specifically.
function getCardDiv() {
    return screen.getAllByRole("button").find(el => el.tagName === "DIV")!;
}

describe("ArtifactCard", () => {
    test("renders the artifact filename", () => {
        renderCard();
        expect(screen.getByText("report.pdf")).toBeInTheDocument();
    });

    test("has role=button and tabIndex=0 when not in preview mode", () => {
        renderCard({ isPreview: false });
        const card = getCardDiv();
        expect(card).toBeInTheDocument();
        expect(card).toHaveAttribute("tabindex", "0");
    });

    test("has no role=button div when in preview mode", () => {
        renderCard({ isPreview: true });
        const divButtons = screen.getAllByRole("button").filter(el => el.tagName === "DIV");
        expect(divButtons).toHaveLength(0);
    });

    test("clicking the card calls setPreviewArtifact when not in preview mode", () => {
        const setPreviewArtifact = vi.fn();
        renderCard({ isPreview: false }, { setPreviewArtifact });
        fireEvent.click(getCardDiv());
        expect(setPreviewArtifact).toHaveBeenCalledWith(mockArtifact);
    });

    test("clicking does not call setPreviewArtifact when in preview mode", () => {
        const setPreviewArtifact = vi.fn();
        renderCard({ isPreview: true }, { setPreviewArtifact });
        const container = screen.getByText("report.pdf").closest("div")!;
        fireEvent.click(container);
        expect(setPreviewArtifact).not.toHaveBeenCalled();
    });

    test("pressing Enter calls setPreviewArtifact when not in preview mode", () => {
        const setPreviewArtifact = vi.fn();
        renderCard({ isPreview: false }, { setPreviewArtifact });
        fireEvent.keyDown(getCardDiv(), { key: "Enter" });
        expect(setPreviewArtifact).toHaveBeenCalledWith(mockArtifact);
    });

    test("pressing Space calls setPreviewArtifact when not in preview mode", () => {
        const setPreviewArtifact = vi.fn();
        renderCard({ isPreview: false }, { setPreviewArtifact });
        fireEvent.keyDown(getCardDiv(), { key: " " });
        expect(setPreviewArtifact).toHaveBeenCalledWith(mockArtifact);
    });
});
