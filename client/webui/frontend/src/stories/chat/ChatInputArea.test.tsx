/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ChatInputArea } from "@/lib/components/chat/ChatInputArea";
import { StoryProvider } from "../mocks/StoryProvider";
import { mockAgentCards } from "../mocks/data";
import { transformAgentCard } from "@/lib/hooks/useAgentCards";
import { SNIP_TO_CHAT_EVENT } from "@/lib/components/chat/preview/Renderers/PdfRenderer";

expect.extend(matchers);

// jsdom does not implement execCommand (used by MentionContentEditable for text insertion)
document.execCommand = vi.fn().mockReturnValue(true);

const mockAgents = mockAgentCards.map(transformAgentCard);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFile(name = "test.png", size = 100, lastModified = Date.now()): File {
    const file = new File(["x".repeat(size)], name, { type: "image/png" });
    Object.defineProperty(file, "lastModified", { value: lastModified });
    return file;
}

function renderComponent(chatContextValues = {}, configContextValues = {}, routerPath = "/") {
    return render(
        <MemoryRouter initialEntries={[routerPath]}>
            <StoryProvider chatContextValues={chatContextValues} configContextValues={configContextValues}>
                <ChatInputArea agents={[]} />
            </StoryProvider>
        </MemoryRouter>
    );
}

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("ChatInputArea rendering", () => {
    test("renders the text input area", () => {
        renderComponent();
        expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    });

    test("send button is disabled when input is empty and not responding", () => {
        renderComponent({ isResponding: false });
        const sendBtn = screen.getByTestId("sendMessage");
        expect(sendBtn).toBeDisabled();
    });

    test("shows agent selector when agents are provided", () => {
        const firstAgent = mockAgents[0];
        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ selectedAgentName: firstAgent.name }}>
                    <ChatInputArea agents={mockAgents} />
                </StoryProvider>
            </MemoryRouter>
        );
        expect(screen.getByText(firstAgent.displayName ?? firstAgent.name ?? "")).toBeInTheDocument();
    });
});

// ---------------------------------------------------------------------------
// Session change useEffect
// ---------------------------------------------------------------------------

describe("session change useEffect", () => {
    test("clears input when session changes", async () => {
        const { rerender } = render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "session-1", pendingPrompt: null }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        const input = screen.getByTestId("chat-input");
        await userEvent.type(input, "hello");
        expect(input).toHaveTextContent("hello");

        rerender(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "session-2", pendingPrompt: null }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(input).toHaveTextContent("");
        });
    });

    test("does not clear input when session is first set (null -> value)", async () => {
        const { rerender } = render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "", pendingPrompt: null }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        const input = screen.getByTestId("chat-input");
        await userEvent.type(input, "keep me");

        rerender(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "session-1", pendingPrompt: null }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        // Input should not be cleared on initial session assignment
        await waitFor(() => {
            expect(input).toHaveTextContent("keep me");
        });
    });

});

// ---------------------------------------------------------------------------
// isResponding useEffect (focus after response ends)
// ---------------------------------------------------------------------------

describe("isResponding useEffect", () => {
    test("focuses input when isResponding transitions from true to false", async () => {
        const { rerender } = render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ isResponding: true }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        rerender(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ isResponding: false }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        await waitFor(
            () => {
                expect(document.activeElement?.getAttribute("contenteditable")).toBe("true");
            },
            { timeout: 300 }
        );
    });
});

// ---------------------------------------------------------------------------
// focus-chat-input custom event useEffect
// ---------------------------------------------------------------------------

describe("focus-chat-input event listener", () => {
    test("focuses input when focus-chat-input event is dispatched", async () => {
        renderComponent();

        act(() => {
            window.dispatchEvent(new Event("focus-chat-input"));
        });

        await waitFor(
            () => {
                expect(document.activeElement?.getAttribute("contenteditable")).toBe("true");
            },
            { timeout: 300 }
        );
    });

});

// ---------------------------------------------------------------------------
// follow-up-question custom event useEffect
// ---------------------------------------------------------------------------

describe("follow-up-question event", () => {
    test("shows context badge when event fires without a prompt", async () => {
        renderComponent();

        act(() => {
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: { text: "selected text", prompt: null, autoSubmit: false, sourceMessageId: null },
                })
            );
        });

        await waitFor(() => {
            expect(screen.getByText(/selected text/)).toBeInTheDocument();
        });
    });

    test("sets input value when event fires with a prompt", async () => {
        renderComponent();

        act(() => {
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: { text: "some context", prompt: "Summarise this", autoSubmit: false, sourceMessageId: null },
                })
            );
        });

        await waitFor(() => {
            const input = screen.getByTestId("chat-input");
            expect(input).toHaveTextContent("Summarise this");
        });
    });

    test("auto-submits when autoSubmit is true and prompt is provided", async () => {
        const handleSubmit = vi.fn().mockResolvedValue(undefined);
        renderComponent({ handleSubmit, isResponding: false });

        act(() => {
            window.dispatchEvent(
                new CustomEvent("follow-up-question", {
                    detail: { text: "context text", prompt: "Do something", autoSubmit: true, sourceMessageId: null },
                })
            );
        });

        await waitFor(() => expect(handleSubmit).toHaveBeenCalled(), { timeout: 500 });
    });
});

// ---------------------------------------------------------------------------
// snip-to-chat custom event useEffect
// ---------------------------------------------------------------------------

describe("snip-to-chat event", () => {
    test("adds file to selected files when snip-to-chat fires", async () => {
        renderComponent();
        const file = makeFile("snip.png");

        act(() => {
            window.dispatchEvent(
                new CustomEvent(SNIP_TO_CHAT_EVENT, {
                    detail: { file },
                })
            );
        });

        await waitFor(() => {
            expect(screen.getByText("snip.png")).toBeInTheDocument();
        });
    });

    test("deduplicates files with same name, size, and lastModified", async () => {
        renderComponent();
        const file = makeFile("snip.png", 100, 1234567890);

        // Fire event twice with the same file
        act(() => {
            window.dispatchEvent(new CustomEvent(SNIP_TO_CHAT_EVENT, { detail: { file } }));
        });
        act(() => {
            window.dispatchEvent(new CustomEvent(SNIP_TO_CHAT_EVENT, { detail: { file } }));
        });

        await waitFor(() => {
            const badges = screen.getAllByText("snip.png");
            expect(badges).toHaveLength(1);
        });
    });

});

// ---------------------------------------------------------------------------
// Pending prompt useEffect
// ---------------------------------------------------------------------------

describe("pending prompt useEffect", () => {
    test("sets input value when pendingPrompt has no variables and agent is selected", async () => {
        const clearPendingPrompt = vi.fn();
        render(
            <MemoryRouter>
                <StoryProvider
                    chatContextValues={{
                        pendingPrompt: { promptText: "Hello world", groupId: "g1", groupName: "G1" },
                        selectedAgentName: "agent-1",
                        clearPendingPrompt,
                    }}
                >
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        await waitFor(() => {
            const input = screen.getByTestId("chat-input");
            expect(input).toHaveTextContent("Hello world");
        });
        expect(clearPendingPrompt).toHaveBeenCalled();
    });

    test("shows variable dialog when pendingPrompt has {{variables}}", async () => {
        render(
            <MemoryRouter>
                <StoryProvider
                    chatContextValues={{
                        pendingPrompt: { promptText: "Hello {{name}}", groupId: "g1", groupName: "G1" },
                        selectedAgentName: "agent-1",
                        clearPendingPrompt: vi.fn(),
                    }}
                >
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        await waitFor(() => {
            // Variable dialog should appear (renders as overlay-backdrop div, not role="dialog")
            expect(screen.getByText("Insert G1")).toBeInTheDocument();
        });
    });

});

// ---------------------------------------------------------------------------
// File handling
// ---------------------------------------------------------------------------

describe("file handling", () => {
    test("selecting a file shows a file badge", async () => {
        renderComponent({ isResponding: false });
        const fileInput = document.querySelector("input[type='file']") as HTMLInputElement;

        const file = makeFile("report.pdf");
        await act(async () => {
            Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
            fireEvent.change(fileInput);
        });

        await waitFor(() => {
            expect(screen.getByText("report.pdf")).toBeInTheDocument();
        });
    });

    test("removing a file badge removes it from the list", async () => {
        renderComponent({ isResponding: false });
        const fileInput = document.querySelector("input[type='file']") as HTMLInputElement;

        const file = makeFile("report.pdf");
        await act(async () => {
            Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
            fireEvent.change(fileInput);
        });

        await waitFor(() => screen.getByText("report.pdf"));

        // Click the remove button on the file badge
        const badge = screen.getByText("report.pdf").closest("div");
        const xBtn = badge?.querySelector("button");
        if (xBtn) {
            await userEvent.click(xBtn);
            await waitFor(() => {
                expect(screen.queryByText("report.pdf")).not.toBeInTheDocument();
            });
        }
    });

    test("duplicate files are not added twice", async () => {
        renderComponent({ isResponding: false });
        const fileInput = document.querySelector("input[type='file']") as HTMLInputElement;

        const file = makeFile("dup.png", 50, 111);

        await act(async () => {
            Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
            fireEvent.change(fileInput);
        });
        await act(async () => {
            Object.defineProperty(fileInput, "files", { value: [file], configurable: true });
            fireEvent.change(fileInput);
        });

        await waitFor(() => {
            const badges = screen.getAllByText("dup.png");
            expect(badges).toHaveLength(1);
        });
    });
});

// ---------------------------------------------------------------------------
// Paste handling
// ---------------------------------------------------------------------------

describe("paste handling", () => {
    test("large pasted text creates a pending badge", async () => {
        renderComponent({ isResponding: false });
        const input = screen.getByTestId("chat-input");

        const largeText = "a".repeat(2000);
        const clipboardData = {
            files: { length: 0 },
            getData: (type: string) => (type === "text" ? largeText : ""),
        };

        fireEvent.paste(input, { clipboardData });

        await waitFor(() => {
            expect(screen.getByText(/snippet/)).toBeInTheDocument();
        });
    });

    test("pasting a file adds it to selected files", async () => {
        renderComponent({ isResponding: false });
        const input = screen.getByTestId("chat-input");

        const file = makeFile("pasted.png");
        const fileList = [file];
        Object.defineProperty(fileList, "length", { value: 1 });

        const clipboardData = {
            files: fileList,
            getData: () => "",
        };

        fireEvent.paste(input, { clipboardData });

        await waitFor(() => {
            expect(screen.getByText("pasted.png")).toBeInTheDocument();
        });
    });

});

// ---------------------------------------------------------------------------
// "/" prompt command trigger
// ---------------------------------------------------------------------------

describe("prompt command trigger", () => {
    test("typing '/' shows the prompts command popup", async () => {
        renderComponent();
        const input = screen.getByTestId("chat-input");

        await userEvent.click(input);
        await userEvent.keyboard("/");

        // PromptsCommand popup should appear
        await waitFor(() => {
            expect(screen.getByTestId("promptCommand")).toBeInTheDocument();
        });
    });
});

// ---------------------------------------------------------------------------
// Location state useEffect (promptText in router state)
// ---------------------------------------------------------------------------

describe("location state promptText useEffect", () => {
    test("calls startNewChatWithPrompt when location state has promptText", async () => {
        const startNewChatWithPrompt = vi.fn().mockResolvedValue(undefined);

        render(
            <MemoryRouter
                initialEntries={[
                    {
                        pathname: "/chat",
                        state: { promptText: "Hello from router", groupId: "g1", groupName: "Group 1" },
                    },
                ]}
            >
                <StoryProvider chatContextValues={{ startNewChatWithPrompt }}>
                    <ChatInputArea agents={[]} />
                </StoryProvider>
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(startNewChatWithPrompt).toHaveBeenCalledWith({
                promptText: "Hello from router",
                groupId: "g1",
                groupName: "Group 1",
            });
        });
    });

});

// ---------------------------------------------------------------------------
// Submit behaviour
// ---------------------------------------------------------------------------

describe("form submission", () => {
    test("calls handleSubmit when form is submitted with text", async () => {
        const handleSubmit = vi.fn().mockResolvedValue(undefined);
        renderComponent({ handleSubmit, isResponding: false });

        const input = screen.getByTestId("chat-input");
        await userEvent.click(input);
        await userEvent.keyboard("Test message");

        const sendBtn = screen.getByTestId("sendMessage");
        await userEvent.click(sendBtn);

        await waitFor(() => {
            expect(handleSubmit).toHaveBeenCalled();
        });
    });

    test("stop button calls handleCancel when responding", () => {
        const handleCancel = vi.fn();
        renderComponent({ isResponding: true, isCancelling: false, handleCancel });

        // When isResponding=true the stop/cancel button replaces send
        const cancelBtn = screen.getByTestId("cancel");
        fireEvent.click(cancelBtn);

        expect(handleCancel).toHaveBeenCalled();
    });
});
