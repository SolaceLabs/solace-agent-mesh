import { useCallback } from "react";
import { api } from "@/lib/api";

/**
 * Hook for automatic chat session title generation.
 * Triggers async generation and polls for completion.
 */
export const useTitleGeneration = () => {
    /**
     * Trigger async title generation with messages.
     * Polls until title is updated or timeout.
     * @param force - If true, forces regeneration even if title already exists (for "Rename with AI")
     */
    const generateTitle = useCallback(async (sessionId: string, userMessage: string, agentResponse: string, currentTitle?: string, force: boolean = false): Promise<void> => {
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
                    const sessionData = await api.webui.get(`/api/v1/sessions/${sessionId}`);
                    initialTitle = sessionData?.data?.name || "New Chat";
                } catch (error) {
                    console.error("[useTitleGeneration] Error fetching initial title:", error);
                    initialTitle = "New Chat";
                }
            }

            console.log(`[useTitleGeneration] Initial title: "${initialTitle}"`);

            // Dispatch event to indicate title generation is starting
            if (typeof window !== "undefined") {
                window.dispatchEvent(
                    new CustomEvent("session-title-generating", {
                        detail: { sessionId, isGenerating: true },
                    })
                );
            }

            // Trigger async title generation
            try {
                await api.webui.post(`/api/v1/sessions/${sessionId}/generate-title`, {
                    userMessage,
                    agentResponse,
                    force,
                });
            } catch (error) {
                console.warn("[useTitleGeneration] Title generation failed:", error);
                // Stop generating indicator on failure
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("session-title-generating", {
                            detail: { sessionId, isGenerating: false },
                        })
                    );
                }
                return;
            }

            console.log("[useTitleGeneration] Title generation triggered, polling for update...");

            // Poll for title update with exponential backoff
            const pollForTitle = async () => {
                const delays = [500, 1000, 1500, 2000, 3000, 3000, 3000]; // Total: ~16 seconds max

                for (const delay of delays) {
                    await new Promise(resolve => setTimeout(resolve, delay));

                    try {
                        const sessionData = await api.webui.get(`/api/v1/sessions/${sessionId}`);
                        const currentName = sessionData?.data?.name;

                        if (currentName && currentName !== initialTitle) {
                            // Dispatch event to stop generating indicator
                            if (typeof window !== "undefined") {
                                window.dispatchEvent(
                                    new CustomEvent("session-title-generating", {
                                        detail: { sessionId, isGenerating: false },
                                    })
                                );
                            }
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
                    } catch (error) {
                        console.error("[useTitleGeneration] Error polling for title:", error);
                    }
                }

                console.warn("[useTitleGeneration] Title generation polling timed out - dispatching event anyway");
                // Stop generating indicator on timeout
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("session-title-generating", {
                            detail: { sessionId, isGenerating: false },
                        })
                    );
                    window.dispatchEvent(
                        new CustomEvent("session-title-updated", {
                            detail: { sessionId },
                        })
                    );
                }
            };

            // Start polling in background
            // The polling function handles its own errors and cleanup
            pollForTitle().catch(error => {
                console.error("[useTitleGeneration] Unexpected error in polling:", error);
                // Ensure generating indicator is stopped on unexpected error
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("session-title-generating", {
                            detail: { sessionId, isGenerating: false },
                        })
                    );
                }
            });
        } catch (error) {
            console.error("[useTitleGeneration] Error triggering title generation:", error);
            // Stop generating indicator on error
            if (typeof window !== "undefined") {
                window.dispatchEvent(
                    new CustomEvent("session-title-generating", {
                        detail: { sessionId, isGenerating: false },
                    })
                );
            }
        }
    }, []);

    return { generateTitle };
};
