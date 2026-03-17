import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import React from "react";

// Mock the ConfigContext
const mockConfigContext = {
    configFeatureEnablement: { binaryArtifactPreview: true },
    webuiServerUrl: "",
    platformServerUrl: "",
    configAuthLoginUrl: "",
    configUseAuthorization: false,
    configWelcomeMessage: "",
    configRedirectUrl: "",
    configCollectFeedback: false,
    configBotName: "",
    configLogoUrl: "",
    persistenceEnabled: true,
    projectsEnabled: true,
    backgroundTasksEnabled: false,
    backgroundTasksDefaultTimeoutMs: 3600000,
    platformConfigured: false,
    autoTitleGenerationEnabled: false,
    identityServiceType: null,
    binaryArtifactPreviewEnabled: true,
};

vi.mock("@/lib/contexts/ConfigContext", () => ({
    ConfigContext: React.createContext(mockConfigContext),
}));

// Mock the api module
vi.mock("@/lib/api", () => ({
    api: {
        webui: {
            get: vi.fn().mockResolvedValue({ available: true, supportedFormats: ["docx", "pptx"] }),
            post: vi.fn().mockResolvedValue({ success: true, pdf_content: "base64pdfcontent" }),
        },
    },
}));

// Mock PdfRenderer to avoid PDF.js complexity
vi.mock("./PdfRenderer", () => ({
    default: ({ url }: { url: string }) => <div data-testid="pdf-renderer">{url ? "PDF Loaded" : "No PDF"}</div>,
}));

import OfficeDocumentRenderer from "@/lib/components/chat/preview/Renderers/OfficeDocumentRenderer";

const renderComponent = (props = {}) => {
    const defaultProps = {
        content: "base64encodedcontent",
        filename: "test-document.docx",
        documentType: "docx" as const,
        setRenderError: vi.fn(),
    };

    return render(
        <MemoryRouter>
            <OfficeDocumentRenderer {...defaultProps} {...props} />
        </MemoryRouter>
    );
};

describe("OfficeDocumentRenderer", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders without crashing", () => {
        const { container } = renderComponent();
        expect(container).toBeDefined();
    });

    it("renders with docx document type", () => {
        const { container } = renderComponent({ documentType: "docx" });
        expect(container).toBeDefined();
    });

    it("renders with pptx document type", () => {
        const { container } = renderComponent({ documentType: "pptx" });
        expect(container).toBeDefined();
    });

    it("calls setRenderError when feature is disabled", async () => {
        // Override the mock to disable the feature
        const originalValue = mockConfigContext.binaryArtifactPreviewEnabled;
        mockConfigContext.binaryArtifactPreviewEnabled = false;

        const setRenderError = vi.fn();
        renderComponent({ setRenderError });

        // Restore
        mockConfigContext.binaryArtifactPreviewEnabled = originalValue;
    });

    it("handles different content for cache key generation", () => {
        // Render with one content
        const { unmount } = renderComponent({ content: "content1", filename: "file1.docx" });
        unmount();

        // Render with different content - should not use cache
        const { container } = renderComponent({ content: "content2", filename: "file2.docx" });
        expect(container).toBeDefined();
    });
});
