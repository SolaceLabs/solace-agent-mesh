/// <reference types="@testing-library/jest-dom" />
import { useState } from "react";
import { render, screen, act } from "@testing-library/react";
import { describe, test, expect, afterEach } from "vitest";

import { ChatSurfaceProvider } from "@/lib/providers/ChatSurfaceProvider";
import { useChatSurface } from "@/lib/hooks/useChatSurface";

// Dumps the live surface as JSON plus a button that bumps local state, so a test
// can force a re-render without remounting the provider.
function SurfaceProbe() {
    const [, setTick] = useState(0);
    const surface = useChatSurface();
    return (
        <>
            <pre data-testid="surface">{JSON.stringify(surface)}</pre>
            <button data-testid="rerender" onClick={() => setTick(t => t + 1)}>
                rerender
            </button>
        </>
    );
}

function readSurface() {
    return JSON.parse(screen.getByTestId("surface").textContent || "{}");
}

describe("ChatSurfaceProvider", () => {
    afterEach(() => {
        window.history.replaceState({}, "", "/");
    });

    test("defaults to the full surface when no agentMode param is present", () => {
        window.history.replaceState({}, "", "/#/chat");
        render(
            <ChatSurfaceProvider>
                <SurfaceProbe />
            </ChatSurfaceProvider>
        );
        const surface = readSurface();
        expect(surface.variant).toBe("full");
        expect(surface.navigation).toEqual(["newChat", "appNav", "recentChats"]);
        expect(surface.showAgentSelector).toBe(true);
        expect(surface.showActivityPanel).toBe(true);
        expect(surface.pinnedAgent).toBeNull();
        expect(surface.seedWelcomeBubble).toBe(true);
    });

    test("computes an embedded surface from the /embed/chat route and captures the pinned agent", () => {
        window.history.replaceState({}, "", "/#/embed/chat?agent=WeatherAgent");
        render(
            <ChatSurfaceProvider>
                <SurfaceProbe />
            </ChatSurfaceProvider>
        );
        const surface = readSurface();
        expect(surface.variant).toBe("embedded");
        expect(surface.navigation).toEqual(["recentChats"]);
        expect(surface.showAgentSelector).toBe(false);
        expect(surface.showActivityPanel).toBe(false);
        expect(surface.allowPrompts).toBe(false);
        expect(surface.pinnedAgent).toBe("WeatherAgent");
        expect(surface.seedWelcomeBubble).toBe(false);
        expect(surface.sessionActions).toEqual(["rename", "renameWithAI", "delete"]);
    });

    test("keeps the pinned agent stable after the hash query is later stripped (issue #3)", () => {
        // Embedded tab pins to WeatherAgent...
        window.history.replaceState({}, "", "/#/embed/chat?agent=WeatherAgent");
        render(
            <ChatSurfaceProvider>
                <SurfaceProbe />
            </ChatSurfaceProvider>
        );
        expect(readSurface().pinnedAgent).toBe("WeatherAgent");

        // ...then in-app navigation strips the hash query, and the component re-renders.
        act(() => {
            window.history.replaceState({}, "", "/#/chat");
        });
        act(() => {
            screen.getByTestId("rerender").click();
        });

        // The pinned agent must NOT be re-derived to null — it was captured once at load.
        expect(readSurface().pinnedAgent).toBe("WeatherAgent");
        expect(readSurface().variant).toBe("embedded");
    });
});
