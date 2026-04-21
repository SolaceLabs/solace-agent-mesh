/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for AttachArtifactDialog covering:
 *   - resolveArtifactUri legacy synthesis (falls back to `artifact://{sessionId}/{filename}`
 *     when the /artifacts/all fast endpoint omits `uri`)
 *   - alreadyAttachedUris hiding (dedupe against current chat input)
 *   - multi-select onAttach contract (returns the selected artifacts with
 *     their resolved `uri` populated, regardless of whether the source
 *     record already had one)
 *   - infinite-scroll sentinel → loadMore invocation
 *   - Cancel closes without emitting onAttach
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { AttachArtifactDialog } from "@/lib/components/chat/file/AttachArtifactDialog";
import type { ArtifactWithSession } from "@/lib/api/artifacts";

expect.extend(matchers);

// Mock the artifacts hook so we can control what the dialog renders.
const mockLoadMore = vi.fn();
let mockUseAllArtifactsReturn: {
    data: ArtifactWithSession[];
    isLoading: boolean;
    hasMore: boolean;
    loadMore: () => void;
    isLoadingMore: boolean;
};

vi.mock("@/lib/api/artifacts", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/artifacts")>("@/lib/api/artifacts");
    return {
        ...actual,
        useAllArtifacts: () => mockUseAllArtifactsReturn,
    };
});

// useDebounce is live (400ms by default in the dialog). To avoid sleeping
// in tests, short-circuit it to return the input immediately.
vi.mock("@/lib/hooks", async () => {
    const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
    return {
        ...actual,
        useDebounce: <T,>(value: T) => value,
    };
});

// IntersectionObserver is not available in jsdom — capture the callback so
// tests can fire it directly to simulate the sentinel entering the viewport.
let latestObserverCallback: IntersectionObserverCallback | null = null;

class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    takeRecords = vi.fn(() => [] as IntersectionObserverEntry[]);
    root: Element | Document | null = null;
    rootMargin = "";
    thresholds: ReadonlyArray<number> = [];
    constructor(callback: IntersectionObserverCallback) {
        latestObserverCallback = callback;
    }
}

const makeArtifact = (overrides: Partial<ArtifactWithSession> = {}): ArtifactWithSession => ({
    filename: "notes.txt",
    size: 100,
    mime_type: "text/plain",
    last_modified: "2026-01-01T00:00:00Z",
    uri: "",
    sessionId: "sess-1",
    sessionName: "Session One",
    ...overrides,
});

describe("AttachArtifactDialog", () => {
    beforeEach(() => {
        mockLoadMore.mockReset();
        latestObserverCallback = null;
        vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
        mockUseAllArtifactsReturn = {
            data: [],
            isLoading: false,
            hasMore: false,
            loadMore: mockLoadMore,
            isLoadingMore: false,
        };
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    test("shows empty state when no artifacts are returned", () => {
        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} />);
        expect(screen.getByText(/no artifacts available/i)).toBeInTheDocument();
    });

    test("synthesizes a legacy artifact:// URI when the record has no uri and attaches it", async () => {
        mockUseAllArtifactsReturn.data = [makeArtifact({ filename: "legacy.txt", sessionId: "sess-legacy", uri: "" })];
        const onAttach = vi.fn();
        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={onAttach} />);

        await userEvent.click(screen.getByText("legacy.txt"));
        await userEvent.click(screen.getByRole("button", { name: /attach 1/i }));

        expect(onAttach).toHaveBeenCalledTimes(1);
        const [emitted] = onAttach.mock.calls[0];
        expect(emitted).toHaveLength(1);
        expect(emitted[0].uri).toBe("artifact://sess-legacy/legacy.txt");
        expect(emitted[0].filename).toBe("legacy.txt");
    });

    test("hides artifacts whose URI is already attached", () => {
        mockUseAllArtifactsReturn.data = [makeArtifact({ filename: "already.txt", sessionId: "sess-1", uri: "artifact://sess-1/already.txt" }), makeArtifact({ filename: "fresh.txt", sessionId: "sess-1", uri: "artifact://sess-1/fresh.txt" })];

        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} alreadyAttachedUris={["artifact://sess-1/already.txt"]} />);

        expect(screen.queryByText("already.txt")).not.toBeInTheDocument();
        expect(screen.getByText("fresh.txt")).toBeInTheDocument();
    });

    test("hides session-only artifacts already attached via their synthesized URI", () => {
        // The list entry has no uri; the parent computes its synthesized URI
        // and includes it in alreadyAttachedUris. The dialog must still hide it.
        mockUseAllArtifactsReturn.data = [makeArtifact({ filename: "legacy.txt", sessionId: "sess-x", uri: "" })];

        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} alreadyAttachedUris={["artifact://sess-x/legacy.txt"]} />);

        expect(screen.queryByText("legacy.txt")).not.toBeInTheDocument();
    });

    test("supports multi-select and emits all chosen artifacts on Attach", async () => {
        mockUseAllArtifactsReturn.data = [
            makeArtifact({ filename: "a.txt", sessionId: "s", uri: "artifact://s/a.txt" }),
            makeArtifact({ filename: "b.txt", sessionId: "s", uri: "artifact://s/b.txt" }),
            makeArtifact({ filename: "c.txt", sessionId: "s", uri: "artifact://s/c.txt" }),
        ];
        const onAttach = vi.fn();
        const onClose = vi.fn();
        render(<AttachArtifactDialog isOpen onClose={onClose} onAttach={onAttach} />);

        await userEvent.click(screen.getByText("a.txt"));
        await userEvent.click(screen.getByText("c.txt"));

        const attachBtn = screen.getByRole("button", { name: /attach 2/i });
        await userEvent.click(attachBtn);

        expect(onAttach).toHaveBeenCalledTimes(1);
        const emitted = onAttach.mock.calls[0][0] as ArtifactWithSession[];
        expect(emitted.map(a => a.filename)).toEqual(["a.txt", "c.txt"]);
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    test("Attach button is disabled when nothing is selected", () => {
        mockUseAllArtifactsReturn.data = [makeArtifact({ uri: "artifact://s/x.txt" })];
        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} />);

        const attachBtn = screen.getByRole("button", { name: /^attach$/i });
        expect(attachBtn).toBeDisabled();
    });

    test("Cancel closes without emitting onAttach", async () => {
        const onAttach = vi.fn();
        const onClose = vi.fn();
        mockUseAllArtifactsReturn.data = [makeArtifact({ uri: "artifact://s/x.txt" })];

        render(<AttachArtifactDialog isOpen onClose={onClose} onAttach={onAttach} />);
        await userEvent.click(screen.getByText("notes.txt"));
        await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

        expect(onAttach).not.toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
    });

    test("infinite-scroll sentinel triggers loadMore when it enters the viewport", async () => {
        mockUseAllArtifactsReturn = {
            data: [makeArtifact({ uri: "artifact://s/x.txt" })],
            isLoading: false,
            hasMore: true,
            loadMore: mockLoadMore,
            isLoadingMore: false,
        };

        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} />);

        await waitFor(() => {
            expect(latestObserverCallback).toBeTypeOf("function");
        });

        // Fire the observer with an intersecting entry — mimics the sentinel
        // scrolling into view at the bottom of the list.
        latestObserverCallback?.(
            [
                {
                    isIntersecting: true,
                    intersectionRatio: 1,
                    target: document.createElement("li"),
                    boundingClientRect: {} as DOMRectReadOnly,
                    intersectionRect: {} as DOMRectReadOnly,
                    rootBounds: null,
                    time: 0,
                },
            ],
            {} as IntersectionObserver
        );

        expect(mockLoadMore).toHaveBeenCalled();
    });

    test("search input updates the query value", async () => {
        mockUseAllArtifactsReturn.data = [];
        render(<AttachArtifactDialog isOpen onClose={() => {}} onAttach={() => {}} />);

        const search = screen.getByTestId("attach-artifact-search") as HTMLInputElement;
        fireEvent.change(search, { target: { value: "report" } });

        expect(search.value).toBe("report");
    });
});
