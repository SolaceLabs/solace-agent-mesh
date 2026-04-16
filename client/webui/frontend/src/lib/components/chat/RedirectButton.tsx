import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { Button } from "@/lib/components/ui";
import { api } from "@/lib/api";
import { useChatContext } from "@/lib/hooks";
import { SESSION_STORAGE_KEYS } from "@/lib/utils/sessionStorageKeys";

export interface RedirectData {
    type: "redirect";
    route: string;
    label: string;
    context: string;
    url_params?: Record<string, string>;
    artifacts?: string[];
    source_session_id?: string;
}

interface RedirectButtonProps {
    data: RedirectData;
}

/**
 * Renders a clickable button that navigates the user to another page
 * (e.g., the Builder) with context carried via sessionStorage.
 * If artifacts are specified, copies them to a new session first.
 */
export const RedirectButton: React.FC<RedirectButtonProps> = ({ data }) => {
    const navigate = useNavigate();
    const { displayError } = useChatContext();

    const handleClick = async () => {
        // Generate a new session ID for the destination.
        const destSessionId = uuidv4();

        // Create the destination session so it exists before the Builder page tries to load it.
        try {
            await api.webui.post("/api/v1/sessions", {
                id: destSessionId,
            });
        } catch (err) {
            displayError({ title: "Failed to create session", error: err instanceof Error ? err.message : "An unknown error occurred." });
            return;
        }

        // Copy artifacts to the new session if specified.
        if (data.artifacts && data.artifacts.length > 0 && data.source_session_id) {
            try {
                await api.webui.post(`/api/v1/sessions/${destSessionId}/artifacts/copy`, {
                    source_session_id: data.source_session_id,
                    filenames: data.artifacts,
                });
            } catch (err) {
                displayError({ title: "Artifact copy failed", error: err instanceof Error ? err.message : "Failed to copy artifacts to the new session." });
            }
        }

        // Store redirect data in sessionStorage for the destination page.
        // Sanitize context to prevent stored XSS — strip HTML tags and limit length.
        const sanitizedContext = typeof data.context === "string" ? data.context.replace(/<[^>]*>/g, "").slice(0, 10000) : "";
        sessionStorage.setItem(SESSION_STORAGE_KEYS.REDIRECT_CONTEXT, sanitizedContext);
        sessionStorage.setItem(SESSION_STORAGE_KEYS.REDIRECT_SESSION_ID, destSessionId);
        if (data.artifacts && data.artifacts.length > 0) {
            sessionStorage.setItem(SESSION_STORAGE_KEYS.REDIRECT_ARTIFACTS, JSON.stringify(data.artifacts));
        }

        // Build the route with optional URL params.
        // Trim before validation AND navigation to prevent bypass via leading whitespace.
        let route = (data.route || "").trim();

        // Validate route is a safe same-origin relative path using URL parsing.
        // This catches bypasses like `/\evil.com`, URL-encoded chars, and protocol-relative URLs.
        const ALLOWED_PREFIXES = ["/builder", "/chat", "/prompts"];
        try {
            const parsed = new URL(route, window.location.origin);
            if (parsed.origin !== window.location.origin || !ALLOWED_PREFIXES.some(p => parsed.pathname.startsWith(p))) {
                throw new Error("Blocked");
            }
        } catch {
            displayError({ title: "Invalid redirect", error: "The server provided an unsafe redirect URL." });
            return;
        }

        if (data.url_params && Object.keys(data.url_params).length > 0) {
            const params = new URLSearchParams(Object.fromEntries(Object.entries(data.url_params).map(([k, v]) => [k, String(v)])));
            route += (route.includes("?") ? "&" : "?") + params.toString();
        }

        navigate(route);
    };

    return (
        <div className="my-3">
            <Button variant="default" size="lg" onClick={handleClick} className="gap-2">
                <Sparkles className="h-4 w-4" />
                {data.label || "Go to Builder"}
            </Button>
        </div>
    );
};
