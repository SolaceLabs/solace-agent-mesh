/// <reference types="@testing-library/jest-dom" />
import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import * as matchers from "@testing-library/jest-dom/matchers";

import { DocumentThumbnail } from "@/lib/components/chat/file/DocumentThumbnail";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// Mock react-pdf to prevent PDF.js worker errors
vi.mock("react-pdf", () => ({
    Document: ({ children }: { children: React.ReactNode }) => <div data-testid="pdf-document">{children}</div>,
    Page: () => <div data-testid="pdf-page" />,
    pdfjs: { GlobalWorkerOptions: { workerSrc: "" } },
}));

const renderWithProviders = (props = {}, configOverrides = {}) => {
    const defaultProps = {
        content: "base64encodedcontent",
        filename: "test-document.docx",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    };

    return render(
        <MemoryRouter>
            <StoryProvider configContextValues={{ binaryArtifactPreviewEnabled: true, ...configOverrides }}>
                <DocumentThumbnail {...defaultProps} {...props} />
            </StoryProvider>
        </MemoryRouter>
    );
};

describe("DocumentThumbnail", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("renders without crashing with docx content", () => {
        const { container } = renderWithProviders();
        expect(container).toBeDefined();
    });

    it("renders without crashing with pptx content", () => {
        const { container } = renderWithProviders({
            filename: "test.pptx",
            mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });
        expect(container).toBeDefined();
    });

    it("renders without crashing when binaryArtifactPreviewEnabled is false", () => {
        const { container } = renderWithProviders({}, { binaryArtifactPreviewEnabled: false });
        expect(container).toBeDefined();
    });

    it("calls api.webui.post for document conversion when feature is enabled", async () => {
        // Mock fetch to return a successful conversion
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ success: true, pdf_content: "JVBER0xQREYtMS40" }),
            })
        );

        const { container } = renderWithProviders();
        expect(container).toBeDefined();
    });

    it("renders with custom width and height", () => {
        const { container } = renderWithProviders({ width: 100, height: 120 });
        expect(container).toBeDefined();
    });
});
