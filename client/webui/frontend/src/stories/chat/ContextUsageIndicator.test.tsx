/// <reference types="@testing-library/jest-dom" />
/**
 * Tests for ContextUsageIndicator's post-response polling effect.
 *
 * Verifies the three intentional behavior changes shipped with the perf
 * patch: (1) the poll fires at 1s and 3s after isResponding flips false,
 * (2) the loop exits early once totalTasks increases, and (3) bumping
 * messageCount alone no longer triggers a refetch (the poller is the only
 * trigger now that the messageCount-driven refetch was removed).
 */
import React from "react";
import { render, act } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

interface UsageShape {
    totalTasks: number;
    usagePercentage: number;
    currentContextTokens: number;
    promptTokens: number;
    completionTokens: number;
    cachedTokens: number;
    maxInputTokens: number | null;
    model: string;
    totalMessages: number;
}

function makeUsage(overrides: Partial<UsageShape> = {}): UsageShape {
    return {
        totalTasks: 0,
        usagePercentage: 10,
        currentContextTokens: 100,
        promptTokens: 100,
        completionTokens: 50,
        cachedTokens: 0,
        maxInputTokens: 100_000,
        model: "test-model",
        totalMessages: 0,
        ...overrides,
    };
}

// Per-test mutable state. Reset in beforeEach; mutated by tests through
// helpers below to control mock behavior.
let currentUsage: UsageShape | null;
let isResponding: boolean;
const mockRefetchUsage = vi.fn();

function setUsage(u: UsageShape | null) {
    currentUsage = u;
}
function setResponding(v: boolean) {
    isResponding = v;
}

// Load the component under test with all dependencies mocked. Mirrors the
// pattern from RecentChatsList.test.tsx — vi.doMock + dynamic import live in
// a per-test loader, NOT in beforeEach. Putting them in beforeEach with this
// many doMocks causes the hook to time out before the dynamic import settles.
async function loadComponent() {
    vi.resetModules();
    mockRefetchUsage.mockReset();
    mockRefetchUsage.mockImplementation(async () => ({ data: currentUsage }));

    vi.doMock("@/lib/api/sessions", () => ({
        useSessionContextUsage: () => ({
            data: currentUsage,
            refetch: mockRefetchUsage,
        }),
        useCompactSession: () => ({
            mutateAsync: vi.fn(),
            isPending: false,
        }),
        sessionKeys: {
            chatTasks: (id: string) => ["sessions", "chat-tasks", id],
        },
    }));

    vi.doMock("@/lib/hooks", () => ({
        useChatContext: () => ({
            isResponding,
            selectedAgentName: "agent-x",
        }),
    }));

    vi.doMock("@tanstack/react-query", () => ({
        useQueryClient: () => ({ invalidateQueries: vi.fn() }),
    }));

    // Stub heavy UI primitives so the polling effect under test is the only
    // thing exercised. None of these are needed to observe refetch calls.
    vi.doMock("@/lib/components/ui", () => ({
        Button: ({ children }: { children?: React.ReactNode }) => React.createElement("button", null, children),
        Tooltip: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
        TooltipTrigger: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
        TooltipContent: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
        Progress: () => React.createElement("div"),
    }));

    vi.doMock("@/lib/components/common", () => ({
        ConfirmationDialog: () => React.createElement("div"),
    }));

    // Replace every lucide icon with a tiny stub. The component transitively
    // pulls in modules that import a wide variety of icons; the Proxy keeps
    // the mock exhaustive without listing each one by name.
    //
    // Special-case ``then`` and well-known Symbols: the dynamic ``import()``
    // runtime probes the resolved namespace for a ``.then`` to detect
    // thenables. If we returned the Stub function for ``.then``, the
    // runtime would treat the namespace as a Promise and wait forever for
    // resolve to be called — hanging loadComponent indefinitely.
    vi.doMock("lucide-react", () => {
        const Stub = () => React.createElement("svg");
        const target: Record<string | symbol, unknown> = { __esModule: true };
        return new Proxy(target, {
            get: (t, prop) => {
                if (prop in t) return t[prop];
                if (prop === "then") return undefined;
                if (typeof prop === "symbol") return undefined;
                return Stub;
            },
        });
    });

    const mod = await import("@/lib/components/chat/ContextUsageIndicator");
    return mod.ContextUsageIndicator;
}

describe("ContextUsageIndicator — post-response polling", () => {
    beforeEach(() => {
        currentUsage = makeUsage();
        isResponding = false;
        mockRefetchUsage.mockReset();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    test("fires refetch at 1s and 3s after isResponding flips true→false", async () => {
        // Start in responding=true so the first render captures that state
        // as the baseline; the next render flips to false and arms the poll.
        setResponding(true);
        const ContextUsageIndicator = await loadComponent();
        // Activate fake timers AFTER the dynamic import settles — react-query
        // and other dependencies can schedule real timers during module init
        // and hang under fake timers if activated earlier.
        vi.useFakeTimers();

        const { rerender } = render(
            React.createElement(ContextUsageIndicator, {
                sessionId: "session-1",
                messageCount: 0,
            })
        );

        // Flip to responding=false — this should arm the poll on rerender.
        setResponding(false);
        rerender(
            React.createElement(ContextUsageIndicator, {
                sessionId: "session-1",
                messageCount: 0,
            })
        );

        // No refetch happens before the first delay elapses.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(900);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(0);

        // First attempt fires at 1s.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(200);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(1);

        // Second attempt fires 3s after that (no early exit because
        // totalTasks never increased above the baseline).
        await act(async () => {
            await vi.advanceTimersByTimeAsync(3000);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(2);

        // Loop is bounded — no third attempt.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10_000);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(2);
    });

    test("exits early once totalTasks increases past the baseline", async () => {
        // Baseline: 5 tasks at the moment isResponding flips true.
        setUsage(makeUsage({ totalTasks: 5 }));
        setResponding(true);
        const ContextUsageIndicator = await loadComponent();
        vi.useFakeTimers();

        const { rerender } = render(
            React.createElement(ContextUsageIndicator, {
                sessionId: "session-1",
                messageCount: 0,
            })
        );

        // The new task lands in the DB before the poll runs.
        setUsage(makeUsage({ totalTasks: 6 }));

        // Flip to responding=false to arm the poll. expectedTasks = 5+1 = 6.
        setResponding(false);
        rerender(
            React.createElement(ContextUsageIndicator, {
                sessionId: "session-1",
                messageCount: 0,
            })
        );

        // First attempt at 1s sees totalTasks=6 ≥ expected=6 → loop exits.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(1000);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(1);

        // No second attempt despite reaching the 3s mark.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(5000);
        });
        expect(mockRefetchUsage).toHaveBeenCalledTimes(1);
    });

    test("does not refetch when only messageCount changes", async () => {
        // Stable isResponding=false across the entire test — the only
        // change is messageCount, which the previous implementation used
        // to drive a refetch on every flap.
        setResponding(false);
        const ContextUsageIndicator = await loadComponent();
        vi.useFakeTimers();

        const { rerender } = render(
            React.createElement(ContextUsageIndicator, {
                sessionId: "session-1",
                messageCount: 0,
            })
        );

        // Bump messageCount through multiple values (simulating the
        // status-bubble / intermediate-message flapping the old refetch
        // hook reacted to).
        for (const count of [1, 2, 3, 4, 5]) {
            rerender(
                React.createElement(ContextUsageIndicator, {
                    sessionId: "session-1",
                    messageCount: count,
                })
            );
        }

        // Let plenty of time pass to be sure no deferred refetch fires.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10_000);
        });

        expect(mockRefetchUsage).not.toHaveBeenCalled();
    });
});
