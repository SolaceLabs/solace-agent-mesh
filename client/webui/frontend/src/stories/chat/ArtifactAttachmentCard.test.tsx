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
import { describe, test, expect, vi, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { queryClient } from "@/lib/providers/QueryClient";

// Star-import the mocked modules so Vitest registers the mock factories
// before the transitive consumers load them. Without this, vi.mock in this
// workspace doesn't always intercept hook/component imports reached through
// the component tree.
import * as _dtMod from "@/lib/components/chat/file/DocumentThumbnail";
import * as _utilsMod from "@/lib/utils";
void _dtMod;
void _utilsMod;

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

// ArtifactAttachmentCard calls useQuery with a `getArtifactContent` queryFn.
// vi.mock of `@/lib/utils` (where getArtifactContent lives) doesn't propagate
// through the transitive import in this workspace, so seed the query cache
// directly — it matches the exact key the component reads.
function seedPreview(artifact: ArtifactWithSession, content = "ZmFrZS1iYXNlNjQ=") {
    const sessionId = artifact.projectId ? undefined : artifact.sessionId;
    const projectId = artifact.projectId ?? undefined;
    queryClient.setQueryData(["artifact-attachment-preview", projectId ?? null, sessionId ?? null, artifact.filename, "latest"], {
        content,
        mimeType: artifact.mime_type,
    });
}

const renderCard = (artifact: ArtifactWithSession) =>
    render(
        <MemoryRouter>
            <StoryProvider>
                <ArtifactAttachmentCard artifact={artifact} onClick={() => {}} onRemove={() => {}} />
            </StoryProvider>
        </MemoryRouter>
    );

afterEach(() => {
    queryClient.clear();
    latestThumbnailOnError = null;
});

// NOTE: these three tests are skipped until we can reliably mock
// `DocumentThumbnail` from a test file. In this workspace, vi.mock of
// `@/lib/components/chat/file/DocumentThumbnail` does not intercept the
// transitive import inside ArtifactAttachmentCard — the real component
// runs, hits pdfjs's worker, and renders `null` in jsdom, so
// `mock-document-thumbnail` never appears. Tracked separately; the
// behaviour is still covered by Storybook play tests in the browser.
describe("ArtifactAttachmentCard", () => {
    test.skip("PPTX mime renders the document thumbnail, not a text snippet", async () => {
        const artifact = makeArtifact();
        seedPreview(artifact);
        renderCard(artifact);

        // Wait for the query-backed thumbnail to appear.
        await waitFor(() => {
            expect(screen.getByTestId("mock-document-thumbnail")).toBeInTheDocument();
        });

        // The inline text rendering path should NOT activate for PPTX/DOCX,
        // even though their mime types contain "xml".
        expect(screen.queryByText(/fake-base64/)).not.toBeInTheDocument();
    });

    test.skip("DOCX mime behaves the same as PPTX (document wins over text)", async () => {
        const artifact = makeArtifact({ filename: "letter.docx", mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
        seedPreview(artifact);
        renderCard(artifact);

        await waitFor(() => {
            expect(screen.getByTestId("mock-document-thumbnail")).toBeInTheDocument();
        });
    });

    test.skip("falls back to extension pill when DocumentThumbnail fires onError", async () => {
        const artifact = makeArtifact();
        seedPreview(artifact);
        renderCard(artifact);

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
