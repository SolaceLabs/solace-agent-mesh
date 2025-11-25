import { useCallback } from "react";
import { authenticatedFetch } from "@/lib/utils/api";
import { useConfigContext } from "@/lib/hooks";

/**
 * Hook for automatic chat session title generation.
 * Triggers async generation and polls for completion.
 */
export const useTitleGeneration = () => {
    const { configServerUrl } = useConfigContext();
    const apiPrefix = `${configServerUrl}/api/v1`;

    /**
     * Trigger async title generation with messages.
     * Polls until title is updated or timeout.
     */
    const generateTitle = useCallback(
        async (sessionId: string, userMessage: string, agentResponse: string, currentTitle?: string): Promise<void> => {
            if (!sessionId || sessionId === "" || sessionId === "null") {
                console.warn("[useTitleGeneration] Invalid session ID, skipping title generation");
                return;
            }

            if (!userMessage || !agentResponse) {
                console.warn("[useTitleGeneration] Missing messages, skipping title generation");
                return;
            }

            try {
                // Get current title before triggering generation
                let initialTitle = currentTitle;
                if (!initialTitle) {
                    try {
                        const sessionResponse = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}`, { credentials: "include" });
                        if (sessionResponse.ok) {
                            const sessionData = await sessionResponse.json();
                            initialTitle = sessionData?.data?.name || "New Chat";
                        }
                    } catch (error) {
                        console.error("[useTitleGeneration] Error fetching initial title:", error);
                        initialTitle = "New Chat";
                    }
                }

                console.log(`[useTitleGeneration] Initial title: "${initialTitle}"`);

                // Trigger async title generation
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}/generate-title`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        userMessage,
                        agentResponse,
                    }),
                    credentials: "include",
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({
                        detail: "Failed to trigger title generation",
                    }));
                    console.warn("[useTitleGeneration] Title generation failed:", errorData.detail);
                    return;
                }

                console.log("[useTitleGeneration] Title generation triggered, polling for update...");

                // Poll for title update with exponential backoff
                const pollForTitle = async () => {
                    const delays = [500, 1000, 1500, 2000, 3000, 3000, 3000]; // Total: ~16 seconds max

                    for (const delay of delays) {
                        await new Promise(resolve => setTimeout(resolve, delay));

                        try {
                            const sessionResponse = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}`, { credentials: "include" });

                            if (sessionResponse.ok) {
                                const sessionData = await sessionResponse.json();
                                const currentName = sessionData?.data?.name;

                                if (currentName && currentName !== initialTitle) {
                                    // Dispatch event to update UI
                                    if (typeof window !== "undefined") {
                                        window.dispatchEvent(
                                            new CustomEvent("session-title-updated", {
                                                detail: { sessionId },
                                            })
                                        );
                                    }
                                    return; // Title changed, stop polling
                                }
                            }
                        } catch (error) {
                            console.error("[useTitleGeneration] Error polling for title:", error);
                        }
                    }

                    console.warn("[useTitleGeneration] Title generation polling timed out - dispatching event anyway");
                    if (typeof window !== "undefined") {
                        window.dispatchEvent(
                            new CustomEvent("session-title-updated", {
                                detail: { sessionId },
                            })
                        );
                    }
                };

                // Start polling in background
                pollForTitle();
            } catch (error) {
                console.error("[useTitleGeneration] Error triggering title generation:", error);
            }
        },
        [apiPrefix]
    );

    return { generateTitle };
};
