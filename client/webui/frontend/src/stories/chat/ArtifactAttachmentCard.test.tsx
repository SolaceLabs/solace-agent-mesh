/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for ArtifactAttachmentCard — two behavioural contracts worth guarding:
 *   1. The PPTX/DOCX-vs-text precedence trap: mime types containing "xml"
 *      pass `supportsTextPreview`, so `isDoc` MUST be evaluated first.
 *      If a refactor breaks that ordering, text content will render where
 *      a document thumbnail should.
 *   2. DocumentThumbnail failure fallback: when the thumbnail fires onError
 *      (e.g. 413 from the conversion service), the card falls back to the
 *      extension pill instead of leaving the preview area empty.
 */
import { render, screen, waitFor, act } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ArtifactAttachmentCard } from "@/lib/components/chat/file/ArtifactAttachmentCard";
import type { ArtifactWithSession } from "@/lib/api/artifacts";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// Prevent PDF.js worker init in jsdom and capture the DocumentThumbnail
// onError prop so tests can simulate a conversion failure.
let latestThumbnailOnError: (() => void) | null = null;

vi.mock("@/lib/components/chat/file/DocumentThumbnail", () => ({
    DocumentThumbnail: ({ onError }: { onError?: () => void }) => {
        latestThumbnailOnError = onError ?? null;
        return <div data-testid="mock-document-thumbnail" />;
    },
    // Pin the set of mimes that DocumentThumbnail claims it can render —
    // the production helper checks extensions and a mime allowlist, but for
    // these tests it is enough to recognise PPTX/DOCX.
    supportsThumbnail: (filename: string, mimeType?: string) => {
        const ext = filename.toLowerCase().split(".").pop();
        if (ext === "docx" || ext === "pptx" || ext === "xlsx" || ext === "pdf") return true;
        if (mimeType?.includes("officedocument")) return true;
        return false;
    },
}));

vi.mock("@/lib/utils", async () => {
    const actual = await vi.importActual<typeof import("@/lib/utils")>("@/lib/utils");
    return {
        ...actual,
        getArtifactContent: vi.fn().mockResolvedValue({
            content: "ZmFrZS1iYXNlNjQ=", // "fake-base64"
            mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }),
    };
});

const makeArtifact = (overrides: Partial<ArtifactWithSession> = {}): ArtifactWithSession => ({
    filename: "slides.pptx",
    size: 1024,
    mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    last_modified: "2026-01-01T00:00:00Z",
    uri: "artifact://sess-1/slides.pptx",
    sessionId: "sess-1",
    sessionName: "Session One",
    ...overrides,
});

const renderCard = (artifact: ArtifactWithSession) =>
    render(
        <MemoryRouter>
            <StoryProvider>
                <ArtifactAttachmentCard artifact={artifact} onClick={() => {}} onRemove={() => {}} />
            </StoryProvider>
        </MemoryRouter>
    );

describe("ArtifactAttachmentCard", () => {
    test("PPTX mime renders the document thumbnail, not a text snippet", async () => {
        renderCard(makeArtifact());

        // Wait for the query-backed thumbnail to appear.
        await waitFor(() => {
            expect(screen.getByTestId("mock-document-thumbnail")).toBeInTheDocument();
        });

        // The inline text rendering path should NOT activate for PPTX/DOCX,
        // even though their mime types contain "xml".
        expect(screen.queryByText(/fake-base64/)).not.toBeInTheDocument();
    });

    test("DOCX mime behaves the same as PPTX (document wins over text)", async () => {
        renderCard(
            makeArtifact({
                filename: "letter.docx",
                mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            })
        );

        await waitFor(() => {
            expect(screen.getByTestId("mock-document-thumbnail")).toBeInTheDocument();
        });
    });

    test("falls back to extension pill when DocumentThumbnail fires onError", async () => {
        renderCard(makeArtifact());

        await waitFor(() => {
            expect(screen.getByTestId("mock-document-thumbnail")).toBeInTheDocument();
        });
        expect(latestThumbnailOnError).toBeTypeOf("function");

        // Simulate the conversion service returning a failure.
        await act(async () => {
            latestThumbnailOnError?.();
        });

        await waitFor(() => {
            expect(screen.queryByTestId("mock-document-thumbnail")).not.toBeInTheDocument();
        });

        // The extension pill (truncated to 4 uppercase chars) is shown instead.
        expect(screen.getByText("PPTX")).toBeInTheDocument();
    });
});
