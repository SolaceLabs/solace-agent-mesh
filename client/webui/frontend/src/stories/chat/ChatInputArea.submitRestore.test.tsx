/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for ChatInputArea — input state restoration on submit failure
 * and aggregated upload error reporting.
 */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ChatInputArea } from "@/lib/components/chat/ChatInputArea";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// jsdom does not implement execCommand (used by MentionContentEditable)
document.execCommand = vi.fn().mockReturnValue(true);

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
