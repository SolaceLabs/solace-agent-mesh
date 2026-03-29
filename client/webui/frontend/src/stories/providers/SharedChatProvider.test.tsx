/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { ArtifactInfo, RAGSearchResult } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts/ChatContext";

expect.extend(matchers);

const mockGetSharedArtifactContent = vi.fn();

describe("SharedChatProvider", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let SharedChatProvider: React.ComponentType<any>;
    let useChatContext: () => ChatContextValue;

    beforeEach(async () => {
        vi.resetModules();
        mockGetSharedArtifactContent.mockReset();

        vi.doMock("@/lib/api/share", () => ({
            getSharedArtifactContent: mockGetSharedArtifactContent,
            getSharedSessionView: vi.fn(),
            createShareLink: vi.fn(),
            updateShareLink: vi.fn(),
            deleteShareLink: vi.fn(),
            downloadSharedArtifact: vi.fn(),
            forkSharedChat: vi.fn(),
            useSharedSessionView: vi.fn().mockReturnValue({ data: null, isLoading: false, error: null }),
            useForkSharedChat: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
            shareKeys: {},
        }));

        const providerMod = await import("@/lib/providers/SharedChatProvider");
        SharedChatProvider = providerMod.SharedChatProvider;

        const contextMod = await import("@/lib/hooks/useChatContext");
        useChatContext = contextMod.useChatContext;
    });

    function makeArtifact(overrides: Partial<ArtifactInfo> = {}): ArtifactInfo {
        return {
            filename: "test.txt",
            mime_type: "text/plain",
            size: 100,
            last_modified: "2025-01-01T00:00:00Z",
            ...overrides,
        };
    }

    function renderWithProvider(props: { artifacts?: ArtifactInfo[]; ragData?: RAGSearchResult[]; sessionId?: string; shareId?: string }) {
        let capturedContext: ChatContextValue | null = null;

        function ContextReader() {
            const ctx = useChatContext();
            capturedContext = ctx;
            return React.createElement("div", { "data-testid": "child" }, "Context loaded");
        }

        const result = render(
            React.createElement(
                SharedChatProvider,
                {
                    artifacts: props.artifacts || [],
                    ragData: props.ragData,
                    sessionId: props.sessionId || "session-1",
                    shareId: props.shareId || "share-1",
                },
                React.createElement(ContextReader)
            )
        );

        return { ...result, getContext: () => capturedContext! };
    }

    test("renders children and provides context", () => {
        renderWithProvider({});
        expect(screen.getByTestId("child")).toBeInTheDocument();
    });

    test("provides artifacts via ChatContext", () => {
        const artifacts = [makeArtifact({ filename: "a.txt" }), makeArtifact({ filename: "b.txt" })];
        const { getContext } = renderWithProvider({ artifacts });

        const ctx = getContext();
        expect(ctx.artifacts).toHaveLength(2);
        expect(ctx.artifacts[0].filename).toBe("a.txt");
        expect(ctx.artifacts[1].filename).toBe("b.txt");
    });

    test("marks artifacts with needsEmbedResolution", () => {
        const artifacts = [makeArtifact({ filename: "a.txt" })];
        const { getContext } = renderWithProvider({ artifacts });
        expect(getContext().artifacts[0].needsEmbedResolution).toBe(true);
    });

    test("isCollaborativeSession is true", () => {
        const { getContext } = renderWithProvider({});
        expect(getContext().isCollaborativeSession).toBe(true);
    });

    test("ragData is passed through correctly", () => {
        const ragData: RAGSearchResult[] = [{ query: "test", searchType: "file_search", timestamp: new Date().toISOString(), sources: [] }];
        const { getContext } = renderWithProvider({ ragData });
        expect(getContext().ragData).toEqual(ragData);
    });

    test("ragEnabled is true when ragData has items", () => {
        const ragData: RAGSearchResult[] = [{ query: "test", searchType: "file_search", timestamp: new Date().toISOString(), sources: [] }];
        const { getContext } = renderWithProvider({ ragData });
        expect(getContext().ragEnabled).toBe(true);
    });

    test("ragEnabled is false when ragData is empty", () => {
        const { getContext } = renderWithProvider({ ragData: [] });
        expect(getContext().ragEnabled).toBe(false);
    });

    test("write operations are no-ops and do not throw", () => {
        const { getContext } = renderWithProvider({});
        const ctx = getContext();

        expect(() => ctx.setSessionId("x")).not.toThrow();
        expect(() => ctx.setSessionName("x")).not.toThrow();
        expect(() => ctx.setMessages([])).not.toThrow();
        expect(() => ctx.openDeleteModal({ filename: "file.txt", mime_type: "text/plain", size: 0, last_modified: "" })).not.toThrow();
        expect(() => ctx.closeDeleteModal()).not.toThrow();
        expect(() => ctx.setIsArtifactEditMode(true)).not.toThrow();
        expect(() => ctx.setSelectedArtifactFilenames(new Set())).not.toThrow();
        expect(() => ctx.handleDeleteSelectedArtifacts()).not.toThrow();
        expect(() => ctx.setIsBatchDeleteModalOpen(true)).not.toThrow();
        expect(() => ctx.markArtifactAsDisplayed("file.txt", true)).not.toThrow();
        expect(() => ctx.setArtifacts([])).not.toThrow();
        expect(() => ctx.addNotification("hi", "info")).not.toThrow();
        expect(() => ctx.displayError({ title: "Error", error: "err" })).not.toThrow();
    });

    test("downloadAndResolveArtifact fetches content for shared artifacts", async () => {
        mockGetSharedArtifactContent.mockResolvedValue({ content: "file contents", mimeType: "text/plain" });

        const artifacts = [makeArtifact({ filename: "test.txt", size: 42 })];
        const { getContext } = renderWithProvider({ artifacts, shareId: "share-abc" });

        let result: unknown;
        await act(async () => {
            result = await getContext().downloadAndResolveArtifact("test.txt");
        });

        expect(mockGetSharedArtifactContent).toHaveBeenCalledWith("share-abc", "test.txt");
        expect(result).toEqual(
            expect.objectContaining({
                name: "test.txt",
                mime_type: "text/plain",
                content: "file contents",
                size: 42,
            })
        );
    });

    test("downloadAndResolveArtifact returns null for unknown artifacts", async () => {
        const artifacts = [makeArtifact({ filename: "test.txt" })];
        const { getContext } = renderWithProvider({ artifacts });

        let result: unknown;
        await act(async () => {
            result = await getContext().downloadAndResolveArtifact("nonexistent.txt");
        });

        expect(result).toBeNull();
    });

    test("downloadAndResolveArtifact prevents duplicate downloads", async () => {
        mockGetSharedArtifactContent.mockResolvedValue({ content: "data", mimeType: "text/plain" });

        const artifacts = [makeArtifact({ filename: "test.txt" })];
        const { getContext } = renderWithProvider({ artifacts, shareId: "share-abc" });

        await act(async () => {
            await getContext().downloadAndResolveArtifact("test.txt");
        });

        // Second call should return null due to dedup
        let secondResult: unknown;
        await act(async () => {
            secondResult = await getContext().downloadAndResolveArtifact("test.txt");
        });

        expect(mockGetSharedArtifactContent).toHaveBeenCalledTimes(1);
        expect(secondResult).toBeNull();
    });

    test("sessionId is passed through", () => {
        const { getContext } = renderWithProvider({ sessionId: "my-session" });
        expect(getContext().sessionId).toBe("my-session");
    });

    test("messages is empty array", () => {
        const { getContext } = renderWithProvider({});
        expect(getContext().messages).toEqual([]);
    });

    test("isResponding is false", () => {
        const { getContext } = renderWithProvider({});
        expect(getContext().isResponding).toBe(false);
    });
});
