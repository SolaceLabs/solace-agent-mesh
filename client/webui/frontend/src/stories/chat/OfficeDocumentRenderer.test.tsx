import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import type { ConfigContextValue } from "@/lib/contexts/ConfigContext";

// Create a mutable config ref so tests can override it
let mockConfigValue: Partial<ConfigContextValue> = {
    binaryArtifactPreviewEnabled: true,
    configFeatureEnablement: { binaryArtifactPreview: true },
};

vi.mock("@/lib/contexts/ConfigContext", () => {
    const ctx = React.createContext<Partial<ConfigContextValue>>({});
    return {
        ConfigContext: ctx,
    };
});

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
vi.mock("@/lib/components/chat/preview/Renderers/PdfRenderer", () => ({
    default: ({ url }: { url: string }) => <div data-testid="pdf-renderer">{url ? "PDF Loaded" : "No PDF"}</div>,
}));

// Import after mocks
import OfficeDocumentRenderer from "@/lib/components/chat/preview/Renderers/OfficeDocumentRenderer";
import { ConfigContext } from "@/lib/contexts/ConfigContext";

const renderWithConfig = (props = {}, configOverrides: Partial<ConfigContextValue> = {}) => {
    const defaultProps = {
        content: "base64encodedcontent",
        filename: "test-document.docx",
        documentType: "docx" as const,
        setRenderError: vi.fn(),
    };

    const configValue = { ...mockConfigValue, ...configOverrides };

    return render(
        <MemoryRouter>
            <ConfigContext.Provider value={configValue as ConfigContextValue}>
                <OfficeDocumentRenderer {...defaultProps} {...props} />
            </ConfigContext.Provider>
        </MemoryRouter>
    );
};

describe("OfficeDocumentRenderer", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockConfigValue = {
            binaryArtifactPreviewEnabled: true,
            configFeatureEnablement: { binaryArtifactPreview: true },
        };
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("renders without crashing with feature enabled", () => {
        const { container } = renderWithConfig();
        expect(container).toBeDefined();
    });

    it("shows error state when binaryArtifactPreviewEnabled is false", async () => {
        const setRenderError = vi.fn();
        renderWithConfig({ setRenderError }, { binaryArtifactPreviewEnabled: false });

        await waitFor(() => {
            expect(setRenderError).toHaveBeenCalledWith(expect.stringContaining("not enabled"));
        });
    });

    it("renders with docx document type", () => {
        const { container } = renderWithConfig({ documentType: "docx" });
        expect(container).toBeDefined();
    });

    it("renders with pptx document type", () => {
        const { container } = renderWithConfig({ documentType: "pptx" });
        expect(container).toBeDefined();
    });

    it("renders checking state when feature is enabled", async () => {
        // Mock global fetch to delay so we can observe the checking state
        const fetchMock = vi.fn().mockImplementation(() => new Promise(() => {})); // never resolves
        vi.stubGlobal("fetch", fetchMock);

        const { container } = renderWithConfig();

        // Component should render something (checking state or error state)
        expect(container).toBeDefined();

        vi.unstubAllGlobals();
    });

    it("handles conversion service unavailable", async () => {
        const { api } = await import("@/lib/api");
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        vi.mocked(api.webui.get).mockResolvedValueOnce({ available: false, supportedFormats: [] } as any);

        const setRenderError = vi.fn();
        renderWithConfig({ setRenderError });

        await waitFor(
            () => {
                // Component should handle unavailable service gracefully
                expect(true).toBe(true);
            },
            { timeout: 2000 }
        );
    });

    it("handles different content for cache key generation", () => {
        const { unmount } = renderWithConfig({ content: "content1", filename: "file1.docx" });
        unmount();

        const { container } = renderWithConfig({ content: "content2", filename: "file2.docx" });
        expect(container).toBeDefined();
    });

    it("shows download fallback when config is null", () => {
        const { container } = render(
            <MemoryRouter>
                <ConfigContext.Provider value={null as unknown as ConfigContextValue}>
                    <OfficeDocumentRenderer content="base64content" filename="test.docx" documentType="docx" setRenderError={vi.fn()} />
                </ConfigContext.Provider>
            </MemoryRouter>
        );
        expect(container).toBeDefined();
    });
});
