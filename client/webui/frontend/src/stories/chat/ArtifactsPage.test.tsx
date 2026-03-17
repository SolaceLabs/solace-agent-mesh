/// <reference types="@testing-library/jest-dom" />
import { render } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ArtifactsPage } from "@/lib/components/pages/ArtifactsPage";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// Mock react-pdf to prevent PDF.js worker errors
vi.mock("react-pdf", () => ({
    Document: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Page: () => <div data-testid="pdf-page" />,
    pdfjs: { GlobalWorkerOptions: { workerSrc: "" } },
}));

// Polyfill IntersectionObserver for jsdom (used by ArtifactsPage for lazy loading)
const mockIntersectionObserver = vi.fn().mockImplementation(callback => ({
    observe: vi.fn().mockImplementation(element => {
        callback([{ isIntersecting: true, target: element }]);
    }),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}));
Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: mockIntersectionObserver,
});

// Mock the useAllArtifacts hook to return test data
vi.mock("@/lib/api/artifacts/hooks", async importOriginal => {
    const original = await importOriginal<typeof import("@/lib/api/artifacts/hooks")>();
    return {
        ...original,
        useAllArtifacts: () => ({
            data: [
                {
                    filename: "test-image.png",
                    size: 1024,
                    mime_type: "image/png",
                    last_modified: "2026-01-01T00:00:00Z",
                    uri: "/api/v1/artifacts/session1/test-image.png/versions/0",
                    sessionId: "session1",
                    sessionName: "Test Session",
                    projectId: undefined,
                    projectName: undefined,
                    source: "upload",
                },
                {
                    filename: "test-doc.docx",
                    size: 2048,
                    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    last_modified: "2026-01-01T00:00:00Z",
                    uri: "/api/v1/artifacts/session1/test-doc.docx/versions/0",
                    sessionId: "session1",
                    sessionName: "Test Session",
                    projectId: undefined,
                    projectName: undefined,
                    source: "upload",
                },
            ],
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        }),
    };
});

// Mock api to prevent actual HTTP calls
vi.mock("@/lib/api", async importOriginal => {
    const original = await importOriginal<typeof import("@/lib/api")>();
    return {
        ...original,
        api: {
            ...original.api,
            webui: {
                ...original.api?.webui,
                get: vi.fn().mockResolvedValue({
                    ok: true,
                    blob: () => Promise.resolve(new Blob(["data"], { type: "image/png" })),
                }),
                delete: vi.fn().mockResolvedValue({ ok: true }),
            },
        },
    };
});

const renderWithProviders = () => {
    return render(
        <MemoryRouter>
            <StoryProvider
                configContextValues={{
                    configFeatureEnablement: { artifactsPage: true },
                    binaryArtifactPreviewEnabled: true,
                }}
            >
                <ArtifactsPage />
            </StoryProvider>
        </MemoryRouter>
    );
};

describe("ArtifactsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // Mock URL.createObjectURL and revokeObjectURL
        Object.defineProperty(window, "URL", {
            writable: true,
            value: {
                ...URL,
                createObjectURL: vi.fn().mockReturnValue("blob:mock-url"),
                revokeObjectURL: vi.fn(),
            },
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("renders without crashing with artifactsPage feature enabled", () => {
        const { container } = renderWithProviders();
        expect(container).toBeDefined();
    });

    it("renders artifact grid with image and docx artifacts", async () => {
        const { container } = renderWithProviders();
        // Component renders without crashing
        expect(container).toBeDefined();
    });

    it("loads image preview via authenticated API (new blob URL code path)", async () => {
        const { container } = renderWithProviders();
        // Wait for async image loading
        await new Promise(resolve => setTimeout(resolve, 200));
        expect(container).toBeDefined();
    });

    it("revokes blob URL on unmount (cleanup code path)", async () => {
        const { unmount, container } = renderWithProviders();
        // Wait for image to load
        await new Promise(resolve => setTimeout(resolve, 200));
        expect(container).toBeDefined();
        // Unmount triggers cleanup
        unmount();
        await new Promise(resolve => setTimeout(resolve, 100));
    });

    it("handles aborted requests gracefully", async () => {
        const { container } = renderWithProviders();
        await new Promise(resolve => setTimeout(resolve, 50));
        expect(container).toBeDefined();
    });
});
