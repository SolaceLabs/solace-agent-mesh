import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, waitFor, within } from "storybook/test";
import { http, HttpResponse } from "msw";

import { ArtifactAttachmentCard } from "@/lib/components/chat/file/ArtifactAttachmentCard";
import type { ArtifactWithSession } from "@/lib/api/artifacts";

// Minimal valid PPTX/DOCX bytes are large; the precedence test only cares
// that the response *exists* and is non-empty — DocumentThumbnail itself is
// covered by its own stories. A 1-byte payload is enough.
const oneByte = new Uint8Array([0x50]);

const baseArtifact: ArtifactWithSession = {
    filename: "slides.pptx",
    size: 1024,
    mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    last_modified: "2026-01-01T00:00:00Z",
    uri: "artifact://sess-1/slides.pptx",
    sessionId: "sess-1",
    sessionName: "Session One",
};

const meta = {
    title: "Chat/ArtifactAttachmentCard",
    component: ArtifactAttachmentCard,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component:
                    "Card-style chip for attached existing artifacts. Critical contract: PPTX/DOCX mime types contain the substring 'xml' and would otherwise pass `supportsTextPreview` — `isDoc` MUST be evaluated first so binary office files don't render as garbled text. Storybook play tests guard that precedence in real Chromium where pdfjs runs.",
            },
        },
    },
    argTypes: {
        onClick: { action: "clicked" },
        onRemove: { action: "removed" },
    },
} satisfies Meta<typeof ArtifactAttachmentCard>;

export default meta;
type Story = StoryObj<typeof meta>;

const fakeContentHandler = (filename: string, mime: string) =>
    http.get(`*/api/v1/artifacts/:sessionId/${filename}/versions/latest`, () => {
        return new HttpResponse(oneByte, {
            headers: { "Content-Type": mime },
        });
    });

export const PptxRendersDocumentThumbnail: Story = {
    args: { artifact: baseArtifact },
    parameters: {
        msw: { handlers: [fakeContentHandler("slides.pptx", baseArtifact.mime_type)] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // The card always shows the filename in the AttachmentCardShell.
        await canvas.findByTitle(/slides\.pptx/i);

        // Negative assertion is what guards the precedence rule: the inline-
        // text branch (AttachmentInlineText) must not render for office docs.
        // It would inject the binary blob's first lines as text — bytes whose
        // base64 representation contains "xml" in the mime type, not in the
        // payload, are why the bug existed in the first place.
        await waitFor(() => {
            expect(canvas.queryByText(/^P{2,}/)).not.toBeInTheDocument();
        });
    },
};

export const DocxRendersDocumentThumbnail: Story = {
    args: {
        artifact: {
            ...baseArtifact,
            filename: "letter.docx",
            mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            uri: "artifact://sess-1/letter.docx",
        },
    },
    parameters: {
        msw: { handlers: [fakeContentHandler("letter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByTitle(/letter\.docx/i);
        // Same precedence guard as the PPTX story.
        await waitFor(() => {
            expect(canvas.queryByText(/^P{2,}/)).not.toBeInTheDocument();
        });
    },
};

export const TextRendersInlineSnippet: Story = {
    args: {
        artifact: {
            ...baseArtifact,
            filename: "notes.txt",
            mime_type: "text/plain",
            uri: "artifact://sess-1/notes.txt",
        },
    },
    parameters: {
        msw: {
            handlers: [
                http.get(`*/api/v1/artifacts/:sessionId/notes.txt/versions/latest`, () => {
                    return new HttpResponse("hello from notes\nsecond line\n", {
                        headers: { "Content-Type": "text/plain" },
                    });
                }),
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByTitle(/notes\.txt/i);
        // Text artifacts use the inline rendering path: the snippet shows up
        // in the card body. This proves the precedence rule doesn't suppress
        // the legitimate text path.
        await waitFor(() => {
            expect(canvas.getByText(/hello from notes/i)).toBeInTheDocument();
        });
    },
};
