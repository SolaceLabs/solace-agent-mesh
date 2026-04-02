import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { Button } from "@/lib/components/ui";
import { api } from "@/lib/api";

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

    const handleClick = async () => {
        // Generate a new session ID for the destination.
        const destSessionId = uuidv4();

        // Create the destination session so it exists before the Builder page tries to load it.
        try {
            await api.webui.post("/api/v1/sessions", {
                id: destSessionId,
            });
        } catch (err) {
            console.warn("[SAM-REDIRECT] Failed to create destination session:", err);
        }

        // Copy artifacts to the new session if specified.
        if (data.artifacts && data.artifacts.length > 0 && data.source_session_id) {
            try {
                await api.webui.post(`/api/v1/sessions/${destSessionId}/artifacts/copy`, {
                    source_session_id: data.source_session_id,
                    filenames: data.artifacts,
                });
            } catch (err) {
                // Artifact copy is best-effort — continue with redirect.
                console.warn("[SAM-REDIRECT] Failed to copy artifacts:", err);
            }
        }

        // Store redirect data in sessionStorage for the destination page.
        sessionStorage.setItem("sam_redirect_context", data.context);
        sessionStorage.setItem("sam_redirect_session_id", destSessionId);
        if (data.artifacts && data.artifacts.length > 0) {
            sessionStorage.setItem("sam_redirect_artifacts", JSON.stringify(data.artifacts));
        }

        // Build the route with optional URL params.
        let route = data.route;
        if (data.url_params && Object.keys(data.url_params).length > 0) {
            const params = new URLSearchParams(data.url_params);
            route += (route.includes("?") ? "&" : "?") + params.toString();
        }

        navigate(route);
    };

    return (
        <div className="my-3">
            <Button variant="outline" size="lg" onClick={handleClick} className="gap-2 border-primary/30 bg-primary/5 text-primary hover:bg-primary/10">
                <Sparkles className="h-4 w-4" />
                {data.label || "Go to Builder"}
            </Button>
        </div>
    );
};
