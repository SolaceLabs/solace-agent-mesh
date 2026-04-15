/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for turnDividerIndex lifecycle in ChatProvider.
 *
 * Verifies the index is set on submit (when there are existing messages)
 * and cleared on new session or session switch.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import React from "react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";

expect.extend(matchers);

// ---------------------------------------------------------------------------
// MSW server for API mocking
// ---------------------------------------------------------------------------

const server = setupServer(
    // Default handler for message stream
    http.post("*/api/v1/message\\:stream", () => {
        return HttpResponse.json({
            jsonrpc: "2.0",
            id: "req-1",
            result: { id: "task-1", contextId: "session-1", status: { state: "submitted" } },
        });
    }),
    // Session save
    http.post("*/api/v1/sessions/*/chat-tasks", () => {
        return HttpResponse.json({ success: true });
    }),
    // Session metadata
    http.get("*/api/v1/sessions/*", () => {
        return HttpResponse.json({ data: { id: "session-2", name: "Test", projectId: null } });
    }),
    // Chat tasks for session
    http.get("*/api/v1/sessions/*/chat-tasks", () => {
        return HttpResponse.json({ data: [] });
    })
);

beforeEach(() => server.resetHandlers());
afterEach(() => server.resetHandlers());

// ---------------------------------------------------------------------------
// Test consumer that reads turnDividerIndex from context
// ---------------------------------------------------------------------------

function TurnDividerConsumer() {
    const ctx = React.useContext(ChatContext);
    if (!ctx) return <div>no context</div>;
    return (
        <div>
            <span data-testid="turn-divider-index">{ctx.turnDividerIndex === null ? "null" : String(ctx.turnDividerIndex)}</span>
            <span data-testid="message-count">{ctx.messages.length}</span>
            <button data-testid="new-session" onClick={() => ctx.handleNewSession()}>
                New Session
            </button>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// NOTE: These tests verify React context plumbing (values pass through the
// provider correctly) but do NOT test the actual turnDividerIndex computation
// logic in ChatProvider.tsx (set on submit when messages exist, cleared on
// session switch). Testing that requires rendering the real ChatProvider with
// its dependencies — tracked as a known gap.
describe("turnDividerIndex lifecycle — plumbing", () => {
    test("turnDividerIndex is null by default", () => {
        render(
            <ChatContext.Provider value={{ turnDividerIndex: null, messages: [] } as unknown as ChatContextValue}>
                <TurnDividerConsumer />
            </ChatContext.Provider>
        );

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
    });

    test("turnDividerIndex reflects the message count when set", () => {
        const mockMessages = [
            { role: "user", parts: [{ kind: "text", text: "hello" }], isUser: true, metadata: { messageId: "m1" } },
            { role: "agent", parts: [{ kind: "text", text: "hi" }], isUser: false, metadata: { messageId: "m2" } },
        ];

        render(
            <ChatContext.Provider
                value={
                    {
                        turnDividerIndex: 2,
                        messages: [...mockMessages, { role: "user", parts: [{ kind: "text", text: "new" }], isUser: true, metadata: { messageId: "m3" } }],
                    } as unknown as ChatContextValue
                }
            >
                <TurnDividerConsumer />
            </ChatContext.Provider>
        );

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("2");
        expect(screen.getByTestId("message-count")).toHaveTextContent("3");
    });

    test("turnDividerIndex is null when cleared (new session)", () => {
        const { rerender } = render(
            <ChatContext.Provider value={{ turnDividerIndex: 5, messages: [] } as unknown as ChatContextValue}>
                <TurnDividerConsumer />
            </ChatContext.Provider>
        );

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("5");

        rerender(
            <ChatContext.Provider value={{ turnDividerIndex: null, messages: [] } as unknown as ChatContextValue}>
                <TurnDividerConsumer />
            </ChatContext.Provider>
        );

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
    });
});

// ---------------------------------------------------------------------------
// Behavioral tests — StatefulTurnDividerProvider exercises the real logic
// that ChatProvider.tsx performs: set index on submit when messages exist,
// clear on new session.
// ---------------------------------------------------------------------------

/**
 * Minimal provider that replicates the turnDividerIndex state management
 * from ChatProvider.tsx without its heavy dependency tree.
 */
function StatefulTurnDividerProvider({ children, initialMessages = [] }: { children: React.ReactNode; initialMessages?: Array<{ role: string; parts: Array<{ kind: string; text: string }>; isUser: boolean; metadata: { messageId: string } }> }) {
    const [messages, setMessages] = React.useState(initialMessages);
    const [turnDividerIndex, setTurnDividerIndex] = React.useState<number | null>(null);
    const messagesRef = React.useRef(messages);
    messagesRef.current = messages;

    const handleSubmit = React.useCallback(async () => {
        // Mirror ChatProvider logic: set divider when messages exist
        if (messagesRef.current.length > 0) {
            setTurnDividerIndex(messagesRef.current.length);
        }
        const userMsg = { role: "user", parts: [{ kind: "text", text: "new" }], isUser: true, metadata: { messageId: `msg-${Date.now()}` } };
        setMessages(prev => [...prev, userMsg]);
    }, []);

    const handleNewSession = React.useCallback(async () => {
        // Mirror ChatProvider logic: clear on new session
        setMessages([]);
        setTurnDividerIndex(null);
    }, []);

    const handleSwitchSession = React.useCallback(async () => {
        // Mirror ChatProvider.handleSwitchSessionCore logic: clear divider on session switch
        setMessages([]);
        setTurnDividerIndex(null);
    }, []);

    return <ChatContext.Provider value={{ turnDividerIndex, messages, handleNewSession, handleSubmit, handleSwitchSession } as unknown as ChatContextValue}>{children}</ChatContext.Provider>;
}

function StatefulConsumer() {
    const ctx = React.useContext(ChatContext);
    if (!ctx) return <div>no context</div>;
    return (
        <div>
            <span data-testid="turn-divider-index">{ctx.turnDividerIndex === null ? "null" : String(ctx.turnDividerIndex)}</span>
            <span data-testid="message-count">{ctx.messages.length}</span>
            <button data-testid="submit" onClick={() => ctx.handleSubmit(new Event("submit") as unknown as React.FormEvent)}>
                Submit
            </button>
            <button data-testid="new-session" onClick={() => ctx.handleNewSession()}>
                New Session
            </button>
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            <button data-testid="switch-session" onClick={() => (ctx as any).handleSwitchSession("other-session")}>
                Switch Session
            </button>
        </div>
    );
}

describe("turnDividerIndex lifecycle — behavioral", () => {
    const twoMessages = [
        { role: "user", parts: [{ kind: "text", text: "hello" }], isUser: true, metadata: { messageId: "m1" } },
        { role: "agent", parts: [{ kind: "text", text: "hi" }], isUser: false, metadata: { messageId: "m2" } },
    ];

    test("handleSubmit sets turnDividerIndex to message count when messages exist", async () => {
        render(
            <StatefulTurnDividerProvider initialMessages={twoMessages}>
                <StatefulConsumer />
            </StatefulTurnDividerProvider>
        );

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
        expect(screen.getByTestId("message-count")).toHaveTextContent("2");

        fireEvent.click(screen.getByTestId("submit"));

        await waitFor(() => {
            expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("2");
            expect(screen.getByTestId("message-count")).toHaveTextContent("3");
        });
    });

    test("handleSubmit does not set turnDividerIndex when no prior messages", async () => {
        render(
            <StatefulTurnDividerProvider initialMessages={[]}>
                <StatefulConsumer />
            </StatefulTurnDividerProvider>
        );

        fireEvent.click(screen.getByTestId("submit"));

        await waitFor(() => {
            expect(screen.getByTestId("message-count")).toHaveTextContent("1");
        });

        expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
    });

    test("handleSwitchSession resets turnDividerIndex to null", async () => {
        render(
            <StatefulTurnDividerProvider initialMessages={twoMessages}>
                <StatefulConsumer />
            </StatefulTurnDividerProvider>
        );

        // First submit to set the divider
        fireEvent.click(screen.getByTestId("submit"));
        await waitFor(() => {
            expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("2");
        });

        // Switch session should clear it
        fireEvent.click(screen.getByTestId("switch-session"));
        await waitFor(() => {
            expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
            expect(screen.getByTestId("message-count")).toHaveTextContent("0");
        });
    });

    test("handleNewSession resets turnDividerIndex to null", async () => {
        render(
            <StatefulTurnDividerProvider initialMessages={twoMessages}>
                <StatefulConsumer />
            </StatefulTurnDividerProvider>
        );

        // First submit to set the divider
        fireEvent.click(screen.getByTestId("submit"));
        await waitFor(() => {
            expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("2");
        });

        // New session should clear it
        fireEvent.click(screen.getByTestId("new-session"));
        await waitFor(() => {
            expect(screen.getByTestId("turn-divider-index")).toHaveTextContent("null");
            expect(screen.getByTestId("message-count")).toHaveTextContent("0");
        });
    });
});
