/**
 * Tests for useAgentSelection — agent switch confirmation flow.
 * Verifies dialog gating based on hasConversation and persistence state.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";

describe("useAgentSelection", () => {
    let useAgentSelection: typeof import("@/lib/hooks/useAgentSelection").useAgentSelection;
    let mockHandleNewSession: ReturnType<typeof vi.fn>;
    let mockSetSelectedAgentName: ReturnType<typeof vi.fn>;
    let mockMessages: { isUser: boolean }[];
    let mockSelectedAgentName: string;
    let mockPersistenceEnabled: boolean;
    let mockAgents: { name: string }[];

    beforeEach(async () => {
        vi.resetModules();

        mockHandleNewSession = vi.fn();
        mockSetSelectedAgentName = vi.fn();
        mockMessages = [];
        mockSelectedAgentName = "agent-a";
        mockPersistenceEnabled = false;
        mockAgents = [{ name: "agent-a" }, { name: "agent-b" }];

        vi.doMock("@/lib/hooks/useChatContext", () => ({
            useChatContext: () => ({
                agents: mockAgents,
                messages: mockMessages,
                selectedAgentName: mockSelectedAgentName,
                setSelectedAgentName: mockSetSelectedAgentName,
                handleNewSession: mockHandleNewSession,
            }),
        }));

        vi.doMock("@/lib/hooks/useConfigContext", () => ({
            useConfigContext: () => ({
                persistenceEnabled: mockPersistenceEnabled,
            }),
        }));

        const mod = await import("@/lib/hooks/useAgentSelection");
        useAgentSelection = mod.useAgentSelection;
    });

    test("switches directly when no conversation exists", () => {
        mockMessages = [];

        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-b");
        });

        expect(mockHandleNewSession).toHaveBeenCalled();
        expect(mockSetSelectedAgentName).toHaveBeenCalledWith("agent-b");
        expect(result.current.switchConfirmOpen).toBe(false);
    });

    test("shows confirmation dialog when user has typed and persistence is off", () => {
        mockMessages = [{ isUser: true }];
        mockPersistenceEnabled = false;

        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-b");
        });

        expect(mockHandleNewSession).not.toHaveBeenCalled();
        expect(result.current.switchConfirmOpen).toBe(true);
    });

    test("switches directly when persistence is enabled even with conversation", () => {
        mockMessages = [{ isUser: true }];
        mockPersistenceEnabled = true;

        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-b");
        });

        expect(mockHandleNewSession).toHaveBeenCalled();
        expect(mockSetSelectedAgentName).toHaveBeenCalledWith("agent-b");
        expect(result.current.switchConfirmOpen).toBe(false);
    });

    test("executeSwitch runs after confirm", () => {
        mockMessages = [{ isUser: true }];
        mockPersistenceEnabled = false;

        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-b");
        });

        expect(result.current.switchConfirmOpen).toBe(true);

        act(() => {
            result.current.confirmAgentSwitch();
        });

        expect(mockHandleNewSession).toHaveBeenCalled();
        expect(mockSetSelectedAgentName).toHaveBeenCalledWith("agent-b");
        expect(result.current.switchConfirmOpen).toBe(false);
    });

    test("state resets after cancel", () => {
        mockMessages = [{ isUser: true }];
        mockPersistenceEnabled = false;

        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-b");
        });

        expect(result.current.switchConfirmOpen).toBe(true);

        act(() => {
            result.current.cancelAgentSwitch();
        });

        expect(mockHandleNewSession).not.toHaveBeenCalled();
        expect(result.current.switchConfirmOpen).toBe(false);
    });

    test("no-ops when selecting the same agent", () => {
        const { result } = renderHook(() => useAgentSelection());

        act(() => {
            result.current.handleAgentSelection("agent-a");
        });

        expect(mockHandleNewSession).not.toHaveBeenCalled();
        expect(result.current.switchConfirmOpen).toBe(false);
    });
});
