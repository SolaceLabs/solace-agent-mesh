/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for ChatInputArea — input state restoration on submit failure
 * and aggregated upload error reporting.
 */
import { act, render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ChatInputArea } from "@/lib/components/chat/ChatInputArea";
import type { ArtifactWithSession } from "@/lib/api/artifacts";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// jsdom does not implement execCommand (used by MentionContentEditable)
document.execCommand = vi.fn().mockReturnValue(true);

// IntersectionObserver is not available in jsdom — AttachArtifactDialog uses it
// for its infinite-scroll sentinel. A no-op stub is enough for these tests.
class NoopIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
    takeRecords = vi.fn(() => [] as IntersectionObserverEntry[]);
    root: Element | Document | null = null;
    rootMargin = "";
    thresholds: ReadonlyArray<number> = [];
    constructor(_cb: IntersectionObserverCallback) {
        void _cb;
    }
}
vi.stubGlobal("IntersectionObserver", NoopIntersectionObserver);

// Short-circuit debounce so artifact-dialog searches happen synchronously.
vi.mock("@/lib/hooks", async () => {
    const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
    return {
        ...actual,
        useDebounce: <T,>(value: T) => value,
    };
});

// Control what AttachArtifactDialog shows so tests can pick refs by name.
let mockDialogArtifacts: ArtifactWithSession[] = [];
vi.mock("@/lib/api/artifacts", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/artifacts")>("@/lib/api/artifacts");
    return {
        ...actual,
        useAllArtifacts: () => ({
            data: mockDialogArtifacts,
            isLoading: false,
            hasMore: false,
            loadMore: () => {},
            isLoadingMore: false,
        }),
    };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderComponent(chatContextValues = {}) {
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={chatContextValues}>
                <ChatInputArea agents={[]} />
            </StoryProvider>
        </MemoryRouter>
    );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatInputArea submit failure — input state restoration", () => {
    test("clears input immediately on submit", async () => {
        const handleSubmit = vi.fn().mockResolvedValue(undefined);
        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("my important message");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        // Input should be cleared immediately (before handleSubmit resolves)
        await waitFor(() => {
            expect(input).toHaveTextContent("");
        });
    });

    test("restores input when handleSubmit rejects", async () => {
        const handleSubmit = vi.fn().mockRejectedValue(new Error("Network error"));
        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("my important message");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        // After rejection, the input should be restored
        await waitFor(() => {
            expect(input).toHaveTextContent("my important message");
        });
    });

    test("does not overwrite user input typed during async submit gap on failure", async () => {
        // handleSubmit takes a while to reject — user types new content in the meantime
        let rejectFn: (err: Error) => void;
        const handleSubmit = vi.fn().mockImplementation(
            () =>
                new Promise<void>((_resolve, reject) => {
                    rejectFn = reject;
                })
        );
        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("original message");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        // Input should be cleared immediately
        await waitFor(() => {
            expect(input).toHaveTextContent("");
        });

        // User types new content while submit is in-flight
        await userEvent.click(input);
        await userEvent.keyboard("new content");

        await waitFor(() => {
            expect(input).toHaveTextContent("new content");
        });

        // Now reject the submit
        rejectFn!(new Error("Network error"));

        // Wait for the rejection to be handled
        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });

        // The user's new content should NOT be overwritten by the restore
        await waitFor(() => {
            expect(input).toHaveTextContent("new content");
        });
    });

    test("shows error notification when handleSubmit rejects", async () => {
        const displayError = vi.fn();
        const handleSubmit = vi.fn().mockRejectedValue(new Error("Server error"));
        renderComponent({ handleSubmit, isResponding: false, displayError });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("test");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        await waitFor(() => {
            expect(displayError).toHaveBeenCalledWith(
                expect.objectContaining({
                    title: "Failed to Send Message",
                })
            );
        });
    });
});

// ---------------------------------------------------------------------------
// Aggregated upload error reporting
// ---------------------------------------------------------------------------

describe("ChatInputArea aggregated upload error reporting", () => {
    test("shows consolidated error when pasted text artifact uploads fail", async () => {
        const displayError = vi.fn();
        const handleSubmit = vi.fn().mockResolvedValue(undefined);
        // uploadArtifactFile returns an error object for each upload
        const uploadArtifactFile = vi.fn().mockResolvedValue({ error: "Upload quota exceeded" });

        renderComponent({ handleSubmit, isResponding: false, displayError, uploadArtifactFile });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);

        // Paste large text (>= 2000 chars) to create a pendingPastedTextItem
        const largeText = "x".repeat(2100);
        const clipboardData = {
            getData: (type: string) => (type === "text/plain" || type === "text" ? largeText : ""),
            types: ["text/plain"],
            files: [],
            items: [],
        };

        fireEvent.paste(input, { clipboardData });

        // Wait for the pasted text badge to appear
        await waitFor(() => {
            expect(screen.getByText(/snippet/i)).toBeInTheDocument();
        });

        // Type a message so submit is enabled
        await userEvent.keyboard("send with artifact");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        // The upload should have been attempted
        await waitFor(() => {
            expect(uploadArtifactFile).toHaveBeenCalled();
        });

        // A consolidated error should be shown (not per-item)
        await waitFor(() => {
            expect(displayError).toHaveBeenCalledWith(
                expect.objectContaining({
                    title: "Some uploads failed",
                })
            );
        });

        // The message should still be sent (with whatever succeeded)
        expect(handleSubmit).toHaveBeenCalled();
    });

    test("sends message successfully when no pasted text items fail", async () => {
        const displayError = vi.fn();
        const handleSubmit = vi.fn().mockResolvedValue(undefined);
        const uploadArtifactFile = vi.fn().mockResolvedValue({ uri: "artifact://test.txt", sessionId: "s1" });

        renderComponent({ handleSubmit, isResponding: false, displayError, uploadArtifactFile });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);

        // Paste large text
        const largeText = "y".repeat(2100);
        const clipboardData = {
            getData: (type: string) => (type === "text/plain" || type === "text" ? largeText : ""),
            types: ["text/plain"],
            files: [],
            items: [],
        };

        fireEvent.paste(input, { clipboardData });

        await waitFor(() => {
            expect(screen.getByText(/snippet/i)).toBeInTheDocument();
        });

        await userEvent.keyboard("send with artifact");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });

        // No error should be shown for successful uploads
        expect(displayError).not.toHaveBeenCalledWith(expect.objectContaining({ title: "Some uploads failed" }));
    });
});

// ---------------------------------------------------------------------------
// Attach-dialog helper + fixtures
// ---------------------------------------------------------------------------

const makeArtifact = (overrides: Partial<ArtifactWithSession> = {}): ArtifactWithSession => ({
    filename: "ref.txt",
    size: 100,
    mime_type: "text/plain",
    last_modified: "2026-01-01T00:00:00Z",
    uri: "artifact://sess-1/ref.txt",
    sessionId: "sess-1",
    sessionName: "Session One",
    ...overrides,
});

/** Open the Paperclip dropdown, choose "Attach existing artifact", select
 *  each artifact by filename, and confirm. The paperclip trigger is
 *  aria-labelled "Attach" — there is no other button with exactly that
 *  accessible name before the dialog opens. */
async function attachArtifactsViaDialog(filenames: string[]) {
    await userEvent.click(screen.getByRole("button", { name: "Attach" }));
    await userEvent.click(await screen.findByText(/attach existing artifact/i));

    for (const name of filenames) {
        await userEvent.click(await screen.findByText(name));
    }
    await userEvent.click(screen.getByRole("button", { name: new RegExp(`^attach ${filenames.length}$`, "i") }));
}

// ---------------------------------------------------------------------------
// Wire envelope for attached artifact references
// ---------------------------------------------------------------------------

describe("ChatInputArea — artifact reference envelope", () => {
    test("submit produces a File with application/x-artifact-reference MIME and JSON body", async () => {
        mockDialogArtifacts = [makeArtifact({ filename: "ref.txt", uri: "artifact://sess-1/ref.txt", mime_type: "text/plain" })];
        const handleSubmit = vi.fn().mockResolvedValue(undefined);

        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("hello");

        await attachArtifactsViaDialog(["ref.txt"]);

        await userEvent.click(screen.getByTestId("sendMessage"));

        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });

        // handleSubmit(event, allFiles, fullMessage, sessionId, html, quote, quoteId)
        const files = handleSubmit.mock.calls[0][1] as File[];
        const envelope = files.find(f => f.type === "application/x-artifact-reference");
        expect(envelope).toBeDefined();
        expect(envelope!.name).toBe("ref.txt");

        const body = JSON.parse(await envelope!.text());
        expect(body).toEqual({
            isArtifactReference: true,
            uri: "artifact://sess-1/ref.txt",
            filename: "ref.txt",
            mimeType: "text/plain",
        });
    });
});

// ---------------------------------------------------------------------------
// Restore-on-failure for selectedArtifactRefs
// ---------------------------------------------------------------------------

describe("ChatInputArea — selectedArtifactRefs restore on submit failure", () => {
    test("restores the attached artifact card when handleSubmit rejects", async () => {
        mockDialogArtifacts = [makeArtifact({ filename: "ref.txt", uri: "artifact://sess-1/ref.txt" })];
        const handleSubmit = vi.fn().mockRejectedValue(new Error("Network error"));

        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("attached message");

        await attachArtifactsViaDialog(["ref.txt"]);

        // The attachment card shows the filename in a pill before submit.
        expect(screen.getByTitle("ref.txt")).toBeInTheDocument();

        await userEvent.click(screen.getByTestId("sendMessage"));

        // After the rejection, the artifact card should be restored.
        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });
        await waitFor(() => {
            expect(screen.getByTitle("ref.txt")).toBeInTheDocument();
        });
    });

    test("does not clobber newly-attached artifacts if the user attached a different ref during the async gap", async () => {
        mockDialogArtifacts = [makeArtifact({ filename: "original.txt", uri: "artifact://sess-1/original.txt" }), makeArtifact({ filename: "new.txt", uri: "artifact://sess-1/new.txt" })];
        let rejectFn: (err: Error) => void;
        const handleSubmit = vi.fn().mockImplementation(
            () =>
                new Promise<void>((_resolve, reject) => {
                    rejectFn = reject;
                })
        );

        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("message");

        // Attach the first ref, then submit.
        await attachArtifactsViaDialog(["original.txt"]);
        await userEvent.click(screen.getByTestId("sendMessage"));

        // Card should clear immediately after resetInputState runs.
        await waitFor(() => {
            expect(screen.queryByTitle("original.txt")).not.toBeInTheDocument();
        });

        // User attaches a different artifact while the submit is in flight.
        await attachArtifactsViaDialog(["new.txt"]);
        await waitFor(() => {
            expect(screen.getByTitle("new.txt")).toBeInTheDocument();
        });

        // Now the submit rejects — restore must NOT overwrite the new ref.
        await act(async () => {
            rejectFn!(new Error("Network error"));
        });

        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });

        // Only "new.txt" should remain; the original must not reappear.
        expect(screen.getByTitle("new.txt")).toBeInTheDocument();
        expect(screen.queryByTitle("original.txt")).not.toBeInTheDocument();
    });
});
