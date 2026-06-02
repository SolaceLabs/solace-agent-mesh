/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter, useLocation } from "react-router-dom";

import { EmbeddedRouteGuard } from "@/lib/components/navigation/EmbeddedRouteGuard";
import { ChatSurfaceContext, FULL_CHAT_SURFACE, type ChatSurface } from "@/lib/contexts";

expect.extend(matchers);

const EMBEDDED: ChatSurface = { ...FULL_CHAT_SURFACE, variant: "embedded", showNav: false, showRecentChatsPanel: true, pinnedAgent: "WeatherAgent" };
const EMBEDDED_NO_AGENT: ChatSurface = { ...EMBEDDED, pinnedAgent: null };

function LocationProbe() {
    const loc = useLocation();
    return <div data-testid="loc">{loc.pathname + loc.search}</div>;
}

function renderAt(initial: string, surface: ChatSurface) {
    return render(
        <MemoryRouter initialEntries={[initial]}>
            <ChatSurfaceContext.Provider value={surface}>
                <EmbeddedRouteGuard />
                <LocationProbe />
            </ChatSurfaceContext.Provider>
        </MemoryRouter>
    );
}

describe("EmbeddedRouteGuard", () => {
    beforeEach(() => vi.spyOn(console, "warn").mockImplementation(() => {}));
    afterEach(() => vi.restoreAllMocks());

    test("redirects an off-embed route back to /agent-mode/chat with the pinned agent", async () => {
        renderAt("/projects", EMBEDDED);
        await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/agent-mode/chat?agent=WeatherAgent"));
    });

    test("re-appends a dropped ?agent= on an embed route", async () => {
        renderAt("/agent-mode/chat", EMBEDDED);
        await waitFor(() => expect(screen.getByTestId("loc")).toHaveTextContent("/agent-mode/chat?agent=WeatherAgent"));
    });

    test("leaves a valid embed route (with agent) untouched", () => {
        renderAt("/agent-mode/recent-chats?agent=WeatherAgent", EMBEDDED);
        expect(screen.getByTestId("loc")).toHaveTextContent("/agent-mode/recent-chats?agent=WeatherAgent");
    });

    test("no-agent embed does not loop on /agent-mode/chat", () => {
        renderAt("/agent-mode/chat", EMBEDDED_NO_AGENT);
        expect(screen.getByTestId("loc")).toHaveTextContent("/agent-mode/chat");
    });

    test("full surface never redirects (no-op off embed)", () => {
        renderAt("/projects", FULL_CHAT_SURFACE);
        expect(screen.getByTestId("loc")).toHaveTextContent("/projects");
    });
});
