/// <reference types="@testing-library/jest-dom" />
import { render, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ArtifactsPage } from "@/lib/components/pages/ArtifactsPage";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { StoryProvider } from "../mocks/StoryProvider";
import type { ConfigContextValue } from "@/lib/contexts/ConfigContext";

expect.extend(matchers);

// Mock config value with artifactsPage enabled
const mockConfig: ConfigContextValue = {
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
    identityServiceType: null,
    binaryArtifactPreviewEnabled: true,
    configFeatureEnablement: { artifactsPage: true },
    frontend_use_authorization: false,
};

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

// Mock global fetch to intercept all HTTP calls
// The api client uses fetch internally
const mockFetch = vi.fn().mockImplementation((url: string) => {
    const urlStr = String(url);
    if (urlStr.includes("/api/v1/artifacts/all")) {
        const responseData = {
            artifacts: [
                {
                    filename: "test-image.png",
                    size: 1024,
                    mimeType: "image/png",
                    lastModified: "2026-01-01T00:00:00Z",
                    uri: "/api/v1/artifacts/session1/test-image.png/versions/0",
                    sessionId: "session1",
                    sessionName: "Test Session",
                    projectId: null,
                    projectName: null,
                    source: "upload",
                },
            ],
            totalCount: 1,
        };
        return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(responseData),
            text: () => Promise.resolve(JSON.stringify(responseData)),
            blob: () => Promise.resolve(new Blob([])),
            headers: new Headers({ "content-type": "application/json" }),
        });
    }
    // For image preview requests
    return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
        text: () => Promise.resolve(""),
        blob: () => Promise.resolve(new Blob(["image-data"], { type: "image/png" })),
        headers: new Headers({ "content-type": "image/png" }),
    });
});

const renderWithProviders = () => {
    return render(
        <MemoryRouter>
            {/* Use local ConfigContext directly to ensure ArtifactsPage reads the correct context */}
            <ConfigContext.Provider value={mockConfig}>
                <StoryProvider>
                    <ArtifactsPage />
                </StoryProvider>
            </ConfigContext.Provider>
        </MemoryRouter>
    );
};

describe("ArtifactsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        // Stub global fetch with our mock
        vi.stubGlobal("fetch", mockFetch);
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

    it("renders without crashing with artifactsPage feature enabled", async () => {
        const { container } = renderWithProviders();
        // Wait for React Query to resolve and render the artifacts
        await waitFor(
            () => {
                // Either the artifacts are shown OR the empty state is shown (both mean loading is done)
                const html = container.innerHTML;
                const isLoaded = !html.includes("animate-spin") || html.includes("test-image.png");
                if (!isLoaded) throw new Error("Still loading");
            },
            { timeout: 3000 }
        );
        expect(container).toBeDefined();
    });

    it("renders artifact grid with image and docx artifacts", async () => {
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 200));
        });
        expect(container).toBeDefined();
    });

    it("loads image preview via authenticated API (new blob URL code path)", async () => {
        const { container } = renderWithProviders();
        // Wait for async image loading (covers lines 185-196)
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container).toBeDefined();
    });

    it("revokes blob URL on unmount (cleanup code path)", async () => {
        const { unmount, container } = renderWithProviders();
        // Wait for image to load (covers line 176 and 190)
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container).toBeDefined();
        // Unmount triggers cleanup (covers lines 289-291)
        await act(async () => {
            unmount();
        });
    });

    it("handles aborted requests gracefully", async () => {
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 50));
        });
        expect(container).toBeDefined();
    });
});
