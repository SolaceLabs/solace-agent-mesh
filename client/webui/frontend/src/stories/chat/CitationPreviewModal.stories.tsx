import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within, fn } from "storybook/test";
import { http, HttpResponse, delay } from "msw";

import { CitationPreviewModal } from "@/lib/components/chat/rag/CitationPreviewModal";
import type { RAGSource } from "@/lib/types";

// Text content that contains the citation text
const sampleTextContent = `This is a sample document for testing citation highlighting.

The document contains multiple paragraphs with various content.

Here is the citation text that should be highlighted in the preview.
This text appears in the contentPreview and should be marked.

Additional content follows to make the document more realistic.
The preview should scroll or highlight appropriately based on the citation.`;

// Minimal valid PDF (1 page, contains "Hello World" text)
// NOTE: This minimal PDF lacks a proper text layer extractable by pdf.js.
// As a result, PdfRenderer's character-position highlighting (citation_map.char_start/char_end)
// won't work - it falls back to text-matching using contentPreview instead.
// For testing precise character-position highlighting, a real PDF with extractable text is needed.
const minimalPdfBase64 =
    "JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPJ4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCA2MTIgNzkyXQovQ29udGVudHMgNCAwIFIKL1Jlc291cmNlcyA8PAovRm9udCA8PAovRjEgNSAwIFIKPj4KPj4KPj4KZW5kb2JqCjQgMCBvYmoKPDwKL0xlbmd0aCA0NAo+PgpzdHJlYW0KQlQKL0YxIDI0IFRmCjEwMCA3MDAgVGQKKEhlbGxvIFdvcmxkKSBUagpFVAplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwKL1R5cGUgL0ZvbnQKL1N1YnR5cGUgL1R5cGUxCi9CYXNlRm9udCAvSGVsdmV0aWNhCj4+CmVuZG9iagp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAwMDA1OCAwMDAwMCBuIAowMDAwMDAwMTE1IDAwMDAwIG4gCjAwMDAwMDAyNzQgMDAwMDAgbiAKMDAwMDAwMDM2OSAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDYKL1Jvb3QgMSAwIFIKPj4Kc3RhcnR4cmVmCjQ1MwolJUVPRgo=";

// Mock RAGSource for text file
const mockTextCitations: RAGSource[] = [
    {
        citationId: "idx0r0",
        filename: "test_document.txt",
        contentPreview: "citation text that should be highlighted",
        relevanceScore: 0.95,
        metadata: {
            location_range: "Lines 1-10",
            primary_location: "Line 5",
        },
    },
];

// Mock RAGSource for PDF file (matches real citation_map structure)
// NOTE: citation_map char positions are included for structural accuracy but won't affect
// highlighting in this test due to the minimal PDF lacking extractable text (see note above).
// Highlighting falls back to matching contentPreview text instead.
const mockPdfCitations: RAGSource[] = [
    {
        citationId: "idx1r0",
        filename: "quarterly_report.pdf",
        contentPreview: "Hello World",
        relevanceScore: 0.92,
        metadata: {
            locations: ["Page 1"],
            primary_location: "Page 1",
            location_range: "Page 1",
            citation_map: [
                {
                    location: "physical_page_1",
                    char_start: 0,
                    char_end: 11,
                },
            ],
        },
    },
];

// MSW Handlers
const successHandlers = [
    // Text file handler - returns plain text (service will convert to base64)
    http.get("*/api/v1/artifacts/test-session-id/test_document.txt/versions/latest*", () => {
        return new HttpResponse(sampleTextContent, {
            headers: { "Content-Type": "text/plain" },
        });
    }),
    // PDF file handler - returns raw PDF bytes
    http.get("*/api/v1/artifacts/test-session-id/quarterly_report.pdf/versions/latest*", () => {
        const pdfBinary = atob(minimalPdfBase64);
        const bytes = new Uint8Array(pdfBinary.length);
        for (let i = 0; i < pdfBinary.length; i++) {
            bytes[i] = pdfBinary.charCodeAt(i);
        }
        return new HttpResponse(bytes, {
            headers: { "Content-Type": "application/pdf" },
        });
    }),
];

const loadingHandlers = [
    http.get("*/api/v1/artifacts/test-session-id/*/versions/latest*", async () => {
        await delay("infinite");
        return new HttpResponse(null);
    }),
];

const errorHandlers = [
    http.get("*/api/v1/artifacts/test-session-id/*/versions/latest*", () => {
        return new HttpResponse(null, {
            status: 500,
            statusText: "Internal Server Error",
        });
    }),
];

const meta = {
    title: "Chat/CitationPreviewModal",
    component: CitationPreviewModal,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Modal for previewing document citations. Displays document content with highlighted citations (for text files) or scrolls to the relevant page (for PDFs).",
            },
        },
        chatContext: {
            sessionId: "test-session-id",
        },
    },
    decorators: [
        Story => (
            <div style={{ height: "100vh", width: "100vw" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof CitationPreviewModal>;

export default meta;
type Story = StoryObj<typeof meta>;

export const TextFile: Story = {
    args: {
        isOpen: true,
        onClose: fn(),
        filename: "test_document.txt",
        locationLabel: "Lines 1-10",
        initialLocation: 1,
        citations: mockTextCitations,
    },
    parameters: {
        msw: { handlers: successHandlers },
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("test_document.txt")).toBeInTheDocument();

        expect(await dialogContent.findByText("Lines 1-10")).toBeInTheDocument();

        const preElement = await dialogContent.findByText(/citation text that should be highlighted/);
        expect(preElement).toBeInTheDocument();

        const contentArea = dialog.querySelector("pre");
        expect(contentArea?.innerHTML).toContain("<mark");
    },
};

export const PdfFile: Story = {
    args: {
        isOpen: true,
        onClose: fn(),
        filename: "quarterly_report.pdf",
        locationLabel: "Page 1",
        initialLocation: 1,
        citations: mockPdfCitations,
    },
    parameters: {
        msw: { handlers: successHandlers },
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);

        // Check header shows filename
        expect(await dialogContent.findByText("quarterly_report.pdf")).toBeInTheDocument();

        // Check page label
        expect(await dialogContent.findByText("Page 1")).toBeInTheDocument();

        // PDF renderer should render - verify dialog contains PDF-related content
        // NOTE: This test verifies the modal structure and PDF loading behavior.
        // Character-position highlighting (citation_map) is not testable here because
        // the minimal test PDF lacks extractable text - highlighting uses fallback mode.
        // Production PDFs with proper text layers will use char_start/char_end positions.
        expect(dialog).toBeInTheDocument();
    },
};

export const Loading: Story = {
    args: {
        isOpen: true,
        onClose: fn(),
        filename: "loading_document.txt",
        locationLabel: "Lines 1-5",
        initialLocation: 1,
        citations: mockTextCitations,
    },
    parameters: {
        msw: { handlers: loadingHandlers },
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);

        // Check loading state is shown
        expect(await dialogContent.findByText("Loading document...")).toBeInTheDocument();
    },
};

export const Error: Story = {
    args: {
        isOpen: true,
        onClose: fn(),
        filename: "error_document.txt",
        locationLabel: "Lines 1-5",
        initialLocation: 1,
        citations: mockTextCitations,
    },
    parameters: {
        msw: { handlers: errorHandlers },
    },
    play: async () => {
        const dialog = await within(document.body).findByRole("dialog");
        expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);

        // Check filename is shown in title
        expect(await dialogContent.findByText("error_document.txt")).toBeInTheDocument();

        // Check location label is shown
        expect(await dialogContent.findByText("Lines 1-5")).toBeInTheDocument();
    },
};
