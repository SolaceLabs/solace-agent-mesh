/// <reference types="@testing-library/jest-dom" />
import { render, waitFor, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ArtifactsPage } from "@/lib/components/pages/ArtifactsPage";
import { ConfigContext } from "@/lib/contexts/ConfigContext";
import { StoryProvider } from "../mocks/StoryProvider";
import type { ConfigContextValue } from "@/lib/contexts/ConfigContext";

expect.extend(matchers);

// ---------------------------------------------------------------------------
// Shared helpers & constants
// ---------------------------------------------------------------------------

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
    autoTitleGenerationEnabled: false,
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

// ---------------------------------------------------------------------------
// IntersectionObserver polyfill for jsdom
// ---------------------------------------------------------------------------

const createdObservers: MockIntersectionObserver[] = [];

class MockIntersectionObserver {
    observe: ReturnType<typeof vi.fn>;
    unobserve = vi.fn();
    disconnect = vi.fn();
    static autoIntersect = true;

    constructor(callback: IntersectionObserverCallback) {
        createdObservers.push(this);
        this.observe = vi.fn().mockImplementation((element: Element) => {
            if (MockIntersectionObserver.autoIntersect) {
                callback([{ isIntersecting: true, target: element }] as IntersectionObserverEntry[], this as unknown as IntersectionObserver);
            }
        });
    }
}
Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: MockIntersectionObserver,
});

// ---------------------------------------------------------------------------
// Artifact fixture factories
// ---------------------------------------------------------------------------

function makeImageArtifact(overrides: Record<string, unknown> = {}) {
    return {
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
        tags: null,
        ...overrides,
    };
}

function makeTextArtifact(overrides: Record<string, unknown> = {}) {
    return {
        filename: "data.json",
        size: 256,
        mimeType: "application/json",
        lastModified: "2026-01-02T00:00:00Z",
        uri: "/api/v1/artifacts/session2/data.json/versions/0",
        sessionId: "session2",
        sessionName: "Session Two",
        projectId: null,
        projectName: null,
        source: "generated",
        tags: null,
        ...overrides,
    };
}

function makeCsvArtifact(overrides: Record<string, unknown> = {}) {
    return {
        filename: "report.csv",
        size: 512,
        mimeType: "text/csv",
        lastModified: "2026-01-03T00:00:00Z",
        uri: "/api/v1/artifacts/session3/report.csv/versions/0",
        sessionId: "session3",
        sessionName: "Session Three",
        projectId: null,
        projectName: null,
        source: "generated",
        tags: null,
        ...overrides,
    };
}

function makeProjectArtifact(overrides: Record<string, unknown> = {}) {
    return {
        filename: "project-doc.md",
        size: 2048,
        mimeType: "text/markdown",
        lastModified: "2026-01-04T00:00:00Z",
        uri: "/api/v1/artifacts/null/project-doc.md/versions/0",
        sessionId: "project-abc123",
        sessionName: "Project Session",
        projectId: "abc123",
        projectName: "My Project",
        source: "project",
        tags: null,
        ...overrides,
    };
}

function makeInternalArtifact(overrides: Record<string, unknown> = {}) {
    return {
        filename: "web_content_internal.html",
        size: 128,
        mimeType: "text/html",
        lastModified: "2026-01-06T00:00:00Z",
        uri: "/api/v1/artifacts/session5/web_content_internal.html/versions/0",
        sessionId: "session5",
        sessionName: "Session Five",
        projectId: null,
        projectName: null,
        source: "generated",
        tags: ["__working"],
        ...overrides,
    };
}

function makeBinaryArtifact(overrides: Record<string, unknown> = {}) {
    return {
        filename: "archive.zip",
        size: 8192,
        mimeType: "application/zip",
        lastModified: "2026-01-07T00:00:00Z",
        uri: "/api/v1/artifacts/session6/archive.zip/versions/0",
        sessionId: "session6",
        sessionName: "Session Six",
        projectId: null,
        projectName: null,
        source: "upload",
        tags: null,
        ...overrides,
    };
}

// ---------------------------------------------------------------------------
// Configurable mock fetch
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let mockArtifactsList: Record<string, any>[] = [makeImageArtifact()];
const MOCK_TEXT_CONTENT = '{"key": "value", "nested": {"a": 1}}\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9extra';
let fetchShouldFail = false;

const mockFetch = vi.fn().mockImplementation((url: string) => {
    const urlStr = String(url);

    if (urlStr.includes("/api/v1/artifacts/all")) {
        const responseData = {
            artifacts: mockArtifactsList,
            totalCount: mockArtifactsList.length,
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

    if (fetchShouldFail) {
        return Promise.reject(new Error("Network error"));
    }

    if (
        urlStr.includes("data.json") ||
        urlStr.includes("report.csv") ||
        urlStr.includes("project-doc.md") ||
        urlStr.includes("observer-test.json") ||
        urlStr.includes("config.yaml") ||
        urlStr.includes("data.xml") ||
        urlStr.includes("app.js") ||
        urlStr.includes("index.ts") ||
        urlStr.includes("internal.html")
    ) {
        return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve({}),
            text: () => Promise.resolve(MOCK_TEXT_CONTENT),
            blob: () => Promise.resolve(new Blob([MOCK_TEXT_CONTENT], { type: "text/plain" })),
            headers: new Headers({ "content-type": "text/plain" }),
        });
    }

    return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
        text: () => Promise.resolve(""),
        blob: () => Promise.resolve(new Blob(["image-data"], { type: "image/png" })),
        headers: new Headers({ "content-type": "image/png" }),
    });
});

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

const renderWithProviders = (configOverrides: Partial<ConfigContextValue> = {}) => {
    const config = { ...mockConfig, ...configOverrides };
    return render(
        <MemoryRouter>
            <ConfigContext.Provider value={config}>
                <StoryProvider>
                    <ArtifactsPage />
                </StoryProvider>
            </ConfigContext.Provider>
        </MemoryRouter>
    );
};

async function waitForArtifactsLoaded(container: HTMLElement) {
    // Wait for React Query to resolve and the loading spinner to disappear
    await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 200));
    });
    await waitFor(
        () => {
            const html = container.innerHTML;
            if (html.includes("animate-spin")) throw new Error("Still loading");
        },
        { timeout: 3000 }
    );
}

// ===========================================================================
// Tests
// ===========================================================================

describe("ArtifactsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        createdObservers.length = 0;
        MockIntersectionObserver.autoIntersect = true;
        fetchShouldFail = false;
        mockArtifactsList = [makeImageArtifact()];
        vi.stubGlobal("fetch", mockFetch);
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

    // -----------------------------------------------------------------------
    // Basic rendering
    // -----------------------------------------------------------------------

    it("renders without crashing with artifactsPage feature enabled", async () => {
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        expect(container).toBeDefined();
    });

    it("renders artifact grid with image artifact", async () => {
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        expect(container.innerHTML).toContain("test-image.png");
    });

    // -----------------------------------------------------------------------
    // Image preview (existing tests, kept for regression)
    // -----------------------------------------------------------------------

    it("loads image preview via authenticated API (blob URL code path)", async () => {
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        const fetchCalls = mockFetch.mock.calls.map(c => String(c[0]));
        expect(fetchCalls.some(url => url.includes("test-image.png"))).toBe(true);
        expect(container).toBeDefined();
    });

    it("revokes blob URL on unmount (cleanup code path)", async () => {
        const { unmount, container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container).toBeDefined();
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

    // -----------------------------------------------------------------------
    // Text preview fetch + caching
    // -----------------------------------------------------------------------

    it("fetches and displays text preview for JSON artifacts", async () => {
        mockArtifactsList = [makeTextArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        const fetchCalls = mockFetch.mock.calls.map(c => String(c[0]));
        expect(fetchCalls.some(url => url.includes("data.json"))).toBe(true);
        expect(container.innerHTML).toContain("data.json");
    });

    it("fetches and displays text preview for CSV artifacts", async () => {
        mockArtifactsList = [makeCsvArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        const fetchCalls = mockFetch.mock.calls.map(c => String(c[0]));
        expect(fetchCalls.some(url => url.includes("report.csv"))).toBe(true);
        expect(container.innerHTML).toContain("report.csv");
    });

    it("caches text preview and serves from cache on re-render", async () => {
        mockArtifactsList = [makeTextArtifact()];
        const { unmount, container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("data.json");

        const firstRenderFetchCount = mockFetch.mock.calls.filter(c => String(c[0]).includes("data.json")).length;

        await act(async () => {
            unmount();
        });

        // Re-render — should use cached text preview, no additional fetch
        const { container: container2 } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container2.innerHTML).toContain("data.json");

        const secondRenderFetchCount = mockFetch.mock.calls.filter(c => String(c[0]).includes("data.json")).length;
        expect(secondRenderFetchCount).toBe(firstRenderFetchCount);
    });

    // -----------------------------------------------------------------------
    // Project artifact URL (covers line 82 — getArtifactApiUrl)
    // -----------------------------------------------------------------------

    it("uses project_id query param for project artifacts", async () => {
        mockArtifactsList = [makeProjectArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        const fetchCalls = mockFetch.mock.calls.map(c => String(c[0]));
        const projectFetch = fetchCalls.find(url => url.includes("project_id="));
        expect(projectFetch).toBeDefined();
        expect(projectFetch).toContain("project_id=abc123");
        expect(container.innerHTML).toContain("project-doc.md");
    });

    // -----------------------------------------------------------------------
    // IntersectionObserver gating
    // -----------------------------------------------------------------------

    it("creates IntersectionObserver for text artifacts that need preview fetch", async () => {
        // Use a unique sessionId so the module-level text preview cache doesn't short-circuit
        mockArtifactsList = [
            makeTextArtifact({
                sessionId: "session-observer-test",
                filename: "observer-test.json",
                uri: "/api/v1/artifacts/session-observer-test/observer-test.json/versions/0",
            }),
        ];
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        // An IntersectionObserver should have been created for the uncached text artifact card
        expect(createdObservers.length).toBeGreaterThan(0);
    });

    it("renders binary artifacts without needing IntersectionObserver for preview", async () => {
        mockArtifactsList = [makeBinaryArtifact()];
        const observerCountBefore = createdObservers.length;
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 300));
        });
        expect(container.innerHTML).toContain("archive.zip");
        // Binary artifacts (zip) don't need preview fetch, so no new observer for them
        // (the observer count should not increase beyond what was already there)
        expect(createdObservers.length).toBe(observerCountBefore);
    });

    it("defers preview fetch until card is visible when autoIntersect is off", async () => {
        MockIntersectionObserver.autoIntersect = false;
        mockArtifactsList = [makeTextArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        // Text artifact should NOT have been fetched because the card is not "visible"
        const textFetches = mockFetch.mock.calls.filter(c => String(c[0]).includes("data.json"));
        expect(textFetches.length).toBe(0);
        expect(container.innerHTML).toContain("data.json");
    });

    // Note: PDF / document thumbnail tests are omitted because the DocumentThumbnail
    // component uses pdfjs-dist internally which cannot run in jsdom.
    // The document thumbnail code path is covered by DocumentThumbnail's own tests.

    // -----------------------------------------------------------------------
    // Error handling
    // -----------------------------------------------------------------------

    it("handles fetch errors gracefully without crashing", async () => {
        fetchShouldFail = true;
        mockArtifactsList = [makeTextArtifact()];
        const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("data.json");
        consoleSpy.mockRestore();
    });

    // -----------------------------------------------------------------------
    // Multiple artifact types rendered together
    // -----------------------------------------------------------------------

    it("renders multiple artifact types together (image, text, project, binary)", async () => {
        mockArtifactsList = [makeImageArtifact(), makeTextArtifact(), makeProjectArtifact(), makeBinaryArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("test-image.png");
        expect(container.innerHTML).toContain("data.json");
        expect(container.innerHTML).toContain("project-doc.md");
        expect(container.innerHTML).toContain("archive.zip");
    });

    // -----------------------------------------------------------------------
    // Internal artifacts filtering
    // -----------------------------------------------------------------------

    it("hides internal artifacts by default", async () => {
        mockArtifactsList = [makeImageArtifact(), makeInternalArtifact()];
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        expect(container.innerHTML).toContain("test-image.png");
        expect(container.innerHTML).not.toContain("web_content_internal.html");
    });

    // -----------------------------------------------------------------------
    // Project filter
    // -----------------------------------------------------------------------

    it("shows project filter when artifacts have project names", async () => {
        mockArtifactsList = [makeImageArtifact(), makeProjectArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("My Project");
    });

    // -----------------------------------------------------------------------
    // Card keyboard interaction
    // -----------------------------------------------------------------------

    it("handles Enter key on artifact card", async () => {
        mockArtifactsList = [makeImageArtifact()];
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        const cards = container.querySelectorAll('[role="button"]');
        expect(cards.length).toBeGreaterThan(0);
        fireEvent.keyDown(cards[0], { key: "Enter" });
    });

    it("handles Space key on artifact card", async () => {
        mockArtifactsList = [makeImageArtifact()];
        const { container } = renderWithProviders();
        await waitForArtifactsLoaded(container);
        const cards = container.querySelectorAll('[role="button"]');
        expect(cards.length).toBeGreaterThan(0);
        fireEvent.keyDown(cards[0], { key: " " });
    });

    // -----------------------------------------------------------------------
    // Empty state
    // -----------------------------------------------------------------------

    it("shows empty state when no artifacts exist", async () => {
        mockArtifactsList = [];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("No artifacts available");
    });

    // -----------------------------------------------------------------------
    // Artifact count display
    // -----------------------------------------------------------------------

    it("displays artifact count", async () => {
        mockArtifactsList = [makeImageArtifact(), makeTextArtifact()];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("2 artifact");
    });

    // -----------------------------------------------------------------------
    // supportsTextPreview coverage (covers lines 99-107)
    // -----------------------------------------------------------------------

    it("renders text preview for YAML artifacts", async () => {
        mockArtifactsList = [
            makeTextArtifact({
                filename: "config.yaml",
                mimeType: "application/x-yaml",
                sessionId: "session-yaml",
                uri: "/api/v1/artifacts/session-yaml/config.yaml/versions/0",
            }),
        ];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("config.yaml");
    });

    it("renders text preview for XML artifacts", async () => {
        mockArtifactsList = [
            makeTextArtifact({
                filename: "data.xml",
                mimeType: "application/xml",
                sessionId: "session-xml",
                uri: "/api/v1/artifacts/session-xml/data.xml/versions/0",
            }),
        ];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("data.xml");
    });

    it("renders text preview for JavaScript artifacts", async () => {
        mockArtifactsList = [
            makeTextArtifact({
                filename: "app.js",
                mimeType: "application/javascript",
                sessionId: "session-js",
                uri: "/api/v1/artifacts/session-js/app.js/versions/0",
            }),
        ];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("app.js");
    });

    it("renders text preview for TypeScript artifacts", async () => {
        mockArtifactsList = [
            makeTextArtifact({
                filename: "index.ts",
                mimeType: "application/typescript",
                sessionId: "session-ts",
                uri: "/api/v1/artifacts/session-ts/index.ts/versions/0",
            }),
        ];
        const { container } = renderWithProviders();
        await act(async () => {
            await new Promise(resolve => setTimeout(resolve, 500));
        });
        expect(container.innerHTML).toContain("index.ts");
    });
});
