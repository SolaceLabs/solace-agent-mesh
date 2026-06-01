import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useChatSurface } from "@/lib/hooks";

/**
 * Keeps the embedded surface "locked" to the `/embed/*` routes. If an in-app navigation
 * drifts off the embed routes — or lands on an embed route that dropped the pinned `?agent=`
 * — it redirects back to `/embed/chat?agent=<pinned>`. This is a backstop for any link or
 * `navigate(...)` not already routed through `useChatRoute()`; it does NOT affect full-page
 * navigations (e.g. the IdP login round-trip), which reload and re-derive the surface.
 *
 * Renders nothing. No-op outside the embedded surface.
 */
export const EmbeddedRouteGuard = () => {
    const surface = useChatSurface();
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        if (surface.variant !== "embedded") return;

        const offEmbed = !location.pathname.startsWith("/embed/");
        // Only enforce agent presence when there's a pinned agent to re-append — otherwise a
        // genuine no-agent embed (`/embed/chat` with no ?agent=) would redirect to itself forever.
        const lostAgent = !!surface.pinnedAgent && !new URLSearchParams(location.search).get("agent");

        if (offEmbed || lostAgent) {
            const target = surface.pinnedAgent ? `/embed/chat?agent=${encodeURIComponent(surface.pinnedAgent)}` : "/embed/chat";
            console.warn("Embedded surface: blocked navigation off the embedded route, returning to", target);
            navigate(target, { replace: true });
        }
    }, [location, surface, navigate]);

    return null;
};
