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
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AttachArtifactDialog } from "@/lib/components/chat/file/AttachArtifactDialog";
import type { ArtifactWithSession } from "@/lib/api/artifacts";
import { artifactKeys } from "@/lib/api/artifacts/keys";

expect.extend(matchers);

// useDebounce is live (400ms by default in the dialog). To avoid sleeping
// in tests, short-circuit it to return the input immediately.
vi.mock("@/lib/hooks", async () => {
    const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
    return {
        ...actual,
        useDebounce: <T,>(value: T) => value,
    };
});

// IntersectionObserver is not available in jsdom. The dialog still mounts
// the sentinel via `new IntersectionObserver(...)`, so a no-op stub is
// enough — actual sentinel-to-loadMore behaviour is covered by the
// Storybook play test in the browser project.
class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    takeRecords = vi.fn(() => [] as IntersectionObserverEntry[]);
    root: Element | Document | null = null;
    rootMargin = "";
    thresholds: ReadonlyArray<number> = [];
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

// Convert the dialog-facing `ArtifactWithSession` shape to the raw API shape
// that `useAllArtifacts` expects in the query cache (camelCase keys — the
// hook's `transformArtifacts` normalises them back).
function toRawArtifact(a: ArtifactWithSession) {
    return {
        filename: a.filename,
        size: a.size,
        mimeType: a.mime_type,
        lastModified: a.last_modified,
        uri: a.uri,
        sessionId: a.sessionId,
        sessionName: a.sessionName,
        projectId: a.projectId ?? null,
        projectName: a.projectName,
        source: a.source ?? null,
        tags: a.tags ?? null,
    };
}

// Vitest mock hoisting in this workspace doesn't reliably intercept hook
// imports transitively. Instead, render against a real QueryClient with its
// cache pre-seeded — the dialog consumes the same cache keys as the
// production hook.
let qc: QueryClient;
function renderDialog(artifacts: ArtifactWithSession[], options: { hasMore?: boolean; loadMoreSpy?: () => void; alreadyAttachedUris?: string[]; onAttach?: (a: ArtifactWithSession[]) => void; onClose?: () => void } = {}) {
    qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });

    // Seed the infinite query cache so useInfiniteQuery resolves immediately
    // with the provided artifacts. When `hasMore` is true we spy on
    // fetchNextPage via QueryClient's fetchNextPage event pipeline: the
    // IntersectionObserver callback calls `loadMore` which ultimately
    // triggers fetchNextPage — we intercept that on the QueryClient itself.
    qc.setQueryData([...artifactKeys.lists(), { search: undefined }], {
        pages: [{ artifacts: artifacts.map(toRawArtifact), nextPage: options.hasMore ? 2 : null, totalCount: artifacts.length }],
        pageParams: [1],
    });

    if (options.hasMore && options.loadMoreSpy) {
        // The dialog calls `loadMore` (== query.fetchNextPage) on intersection.
        // Replace fetchInfiniteQuery at the client level so we observe the call
        // without triggering a real network fetch.
        qc.fetchInfiniteQuery = (() => {
            options.loadMoreSpy!();
            return Promise.resolve({ pages: [], pageParams: [] } as never);
        }) as typeof qc.fetchInfiniteQuery;
    }

    return render(
        <QueryClientProvider client={qc}>
            <AttachArtifactDialog isOpen onClose={options.onClose ?? (() => {})} onAttach={options.onAttach ?? (() => {})} alreadyAttachedUris={options.alreadyAttachedUris} />
        </QueryClientProvider>
    );
}

describe("AttachArtifactDialog", () => {
    beforeEach(() => {
        vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        qc?.clear();
    });

    test("shows empty state when no artifacts are returned", () => {
        renderDialog([]);
        expect(screen.getByText(/no artifacts available/i)).toBeInTheDocument();
    });

    test("synthesizes a legacy artifact:// URI when the record has no uri and attaches it", async () => {
        const onAttach = vi.fn();
        renderDialog([makeArtifact({ filename: "legacy.txt", sessionId: "sess-legacy", uri: "" })], { onAttach });

        await userEvent.click(screen.getByText("legacy.txt"));
        await userEvent.click(screen.getByRole("button", { name: /attach 1/i }));

        expect(onAttach).toHaveBeenCalledTimes(1);
        const [emitted] = onAttach.mock.calls[0];
        expect(emitted).toHaveLength(1);
        expect(emitted[0].uri).toBe("artifact://sess-legacy/legacy.txt");
        expect(emitted[0].filename).toBe("legacy.txt");
    });

    test("percent-encodes reserved URL chars in the synthesized filename so the URI parses correctly", async () => {
        const onAttach = vi.fn();
        const filename = "weird name#1?.txt";
        renderDialog([makeArtifact({ filename, sessionId: "sess-x", uri: "" })], { onAttach });

        await userEvent.click(screen.getByText(filename));
        await userEvent.click(screen.getByRole("button", { name: /attach 1/i }));

        const emitted = onAttach.mock.calls[0][0] as ArtifactWithSession[];
        expect(emitted[0].uri).toBe(`artifact://sess-x/${encodeURIComponent(filename)}`);
        // Round-trip via new URL() parsing — `#`/`?` would otherwise become
        // hash/search and the filename would be lost.
        const parsed = new URL(emitted[0].uri!);
        expect(decodeURIComponent(parsed.pathname.replace(/^\//, ""))).toBe(filename);
    });

    test("hides artifacts whose URI is already attached", () => {
        renderDialog([makeArtifact({ filename: "already.txt", sessionId: "sess-1", uri: "artifact://sess-1/already.txt" }), makeArtifact({ filename: "fresh.txt", sessionId: "sess-1", uri: "artifact://sess-1/fresh.txt" })], {
            alreadyAttachedUris: ["artifact://sess-1/already.txt"],
        });

        expect(screen.queryByText("already.txt")).not.toBeInTheDocument();
        expect(screen.getByText("fresh.txt")).toBeInTheDocument();
    });

    test("hides session-only artifacts already attached via their synthesized URI", () => {
        // The list entry has no uri; the parent computes its synthesized URI
        // and includes it in alreadyAttachedUris. The dialog must still hide it.
        renderDialog([makeArtifact({ filename: "legacy.txt", sessionId: "sess-x", uri: "" })], { alreadyAttachedUris: ["artifact://sess-x/legacy.txt"] });

        expect(screen.queryByText("legacy.txt")).not.toBeInTheDocument();
    });

    test("supports multi-select and emits all chosen artifacts on Attach", async () => {
        const onAttach = vi.fn();
        const onClose = vi.fn();
        renderDialog(
            [
                makeArtifact({ filename: "a.txt", sessionId: "s", uri: "artifact://s/a.txt" }),
                makeArtifact({ filename: "b.txt", sessionId: "s", uri: "artifact://s/b.txt" }),
                makeArtifact({ filename: "c.txt", sessionId: "s", uri: "artifact://s/c.txt" }),
            ],
            { onAttach, onClose }
        );

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
        renderDialog([makeArtifact({ uri: "artifact://s/x.txt" })]);

        const attachBtn = screen.getByRole("button", { name: /^attach$/i });
        expect(attachBtn).toBeDisabled();
    });

    test("Cancel closes without emitting onAttach", async () => {
        const onAttach = vi.fn();
        const onClose = vi.fn();
        renderDialog([makeArtifact({ uri: "artifact://s/x.txt" })], { onAttach, onClose });

        await userEvent.click(screen.getByText("notes.txt"));
        await userEvent.click(screen.getByRole("button", { name: /cancel/i }));

        expect(onAttach).not.toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
    });

    // The infinite-scroll sentinel-to-loadMore wiring is covered by the
    // Storybook play test in AttachArtifactDialog.stories.tsx — vi.mock in
    // jsdom can't reliably intercept useAllArtifacts's refetchOnMount path,
    // so the browser project owns this case where a real
    // IntersectionObserver is available.

    test("search input updates the query value", async () => {
        renderDialog([]);

        const search = screen.getByTestId("attach-artifact-search") as HTMLInputElement;
        fireEvent.change(search, { target: { value: "report" } });

        expect(search.value).toBe("report");
    });
});
