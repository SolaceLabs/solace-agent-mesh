import { useCallback, useEffect, useRef } from "react";
import { v4 } from "uuid";
import { authenticatedFetch, getAccessToken } from "@/lib/utils/api";
import { useThemeContext, useConfigContext } from "@/lib/hooks";
import type { Message, SendStreamingMessageRequest, SendStreamingMessageSuccessResponse, TaskStatusUpdateEvent } from "@/lib/types";

export function useSamSdkHost(appId: string) {
    const { currentTheme } = useThemeContext();
    const { configServerUrl } = useConfigContext();
    const apiPrefix = `${configServerUrl}/api/v1`;

    // Keep track of active SSE connections to clean them up if the component unmounts
    const activeConnections = useRef<Map<string, EventSource>>(new Map());

    useEffect(() => {
        return () => {
            // Cleanup all active connections on unmount
            activeConnections.current.forEach((source) => source.close());
            activeConnections.current.clear();
        };
    }, []);

    const handleMessage = useCallback(
        async (event: MessageEvent) => {
            const { type, id, payload } = event.data;
            if (!type || !type.startsWith("sam:")) return;

            const sourceWindow = event.source as Window;

            const sendToChild = (msgType: string, msgPayload: any) => {
                sourceWindow.postMessage(
                    {
                        type: msgType,
                        id, // Correlate with the original request ID
                        payload: msgPayload,
                    },
                    { targetOrigin: "*" }
                );
            };

            const sendError = (errorMessage: string) => {
                sendToChild(`${type}:error`, { error: errorMessage });
            };

            try {
                switch (type) {
                    case "sam:init":
                        sendToChild("sam:ready", { theme: currentTheme });
                        break;

                    case "sam:theme:get":
                        sendToChild("sam:theme:response", { theme: currentTheme });
                        break;

                    case "sam:agent:call":
                        // 1. Construct the A2A Message
                        const { agentName, prompt, context } = payload;
                        
                        const a2aMessage: Message = {
                            role: "user",
                            parts: [{ kind: "text", text: prompt }],
                            messageId: `msg-${v4()}`,
                            kind: "message",
                            metadata: {
                                agent_name: agentName,
                                app_id: appId, // Enforce app context
                                ...context
                            },
                        };

                        // 2. Start the Task via HTTP
                        const req: SendStreamingMessageRequest = {
                            jsonrpc: "2.0",
                            id: `req-${v4()}`,
                            method: "message/stream",
                            params: { message: a2aMessage },
                        };

                        const initRes = await authenticatedFetch(`${apiPrefix}/message:stream`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(req),
                        });

                        if (!initRes.ok) throw new Error(await initRes.text());
                        
                        const initData = await initRes.json();
                        const taskId = initData.result?.id;
                        
                        if (!taskId) throw new Error("Failed to start agent task");

                        // 3. Subscribe to SSE for this Task
                        const token = getAccessToken();
                        const sseUrl = `${apiPrefix}/sse/subscribe/${taskId}${token ? `?token=${token}` : ""}`;
                        const eventSource = new EventSource(sseUrl, { withCredentials: true });
                        
                        activeConnections.current.set(id, eventSource);

                        let accumulatedText = "";
                        const accumulatedArtifacts: string[] = [];

                        eventSource.addEventListener("status_update", (e) => {
                            try {
                                const data = JSON.parse(e.data) as SendStreamingMessageSuccessResponse;
                                const result = data.result as TaskStatusUpdateEvent;
                                
                                if (result.status?.message?.parts) {
                                    for (const part of result.status.message.parts) {
                                        // Handle Text Streaming
                                        if (part.kind === "text" && part.text) {
                                            sendToChild("sam:agent:stream", { text: part.text });
                                            accumulatedText += part.text;
                                        }
                                        
                                        // Handle Artifacts
                                        if (part.kind === "artifact" && part.status === "completed") {
                                            sendToChild("sam:agent:artifact", { 
                                                name: part.name,
                                                file: part.file 
                                            });
                                            accumulatedArtifacts.push(part.name);
                                        }

                                        // Handle Status/Progress
                                        if (part.kind === "data") {
                                            const meta = part.data as any;
                                            if (meta?.type === "agent_progress_update") {
                                                sendToChild("sam:agent:status", { status: meta.status_text });
                                            }
                                        }
                                    }
                                }
                            } catch (err) {
                                console.error("Error parsing SSE", err);
                            }
                        });

                        eventSource.addEventListener("final_response", () => {
                            // Task Complete
                            sendToChild("sam:agent:response", {
                                response: accumulatedText,
                                artifacts: accumulatedArtifacts
                            });
                            eventSource.close();
                            activeConnections.current.delete(id);
                        });

                        eventSource.addEventListener("error", (e) => {
                            console.error("SSE Error", e);
                            sendError("Connection to agent lost");
                            eventSource.close();
                            activeConnections.current.delete(id);
                        });
                        break;

                    case "sam:storage:get":
                    case "sam:storage:set":
                    case "sam:storage:delete":
                    case "sam:storage:list":
                    case "sam:storage:clear":
                        let url = `/api/v1/apps/${appId}/storage`;
                        let method = "GET";
                        let body = undefined;

                        if (type === "sam:storage:get") {
                            url += `/${encodeURIComponent(payload.key)}`;
                        } else if (type === "sam:storage:set") {
                            url += `/${encodeURIComponent(payload.key)}`;
                            method = "PUT";
                            body = JSON.stringify({ value: payload.value });
                        } else if (type === "sam:storage:delete") {
                            url += `/${encodeURIComponent(payload.key)}`;
                            method = "DELETE";
                        } else if (type === "sam:storage:list") {
                            if (payload.prefix) url += `?prefix=${encodeURIComponent(payload.prefix)}`;
                        } else if (type === "sam:storage:clear") {
                            method = "DELETE";
                        }

                        const storageRes = await authenticatedFetch(url, {
                            method,
                            headers: body ? { "Content-Type": "application/json" } : undefined,
                            body,
                        });

                        if (storageRes.status === 404 && type === "sam:storage:get") {
                            sendToChild("sam:storage:response", { value: null });
                        } else if (!storageRes.ok) {
                            throw new Error(await storageRes.text());
                        } else {
                            const data = await storageRes.json().catch(() => ({}));
                            sendToChild("sam:storage:response", data);
                        }
                        break;

                    case "sam:artifact:upload":
                        const byteCharacters = atob(payload.data);
                        const byteNumbers = new Array(byteCharacters.length);
                        for (let i = 0; i < byteCharacters.length; i++) {
                            byteNumbers[i] = byteCharacters.charCodeAt(i);
                        }
                        const byteArray = new Uint8Array(byteNumbers);
                        const blob = new Blob([byteArray], { type: payload.type });
                        const file = new File([blob], payload.name, { type: payload.type });

                        const formData = new FormData();
                        formData.append("upload_file", file);
                        formData.append("filename", payload.name);

                        const uploadRes = await authenticatedFetch("/api/v1/artifacts/upload", {
                            method: "POST",
                            body: formData,
                        });

                        if (!uploadRes.ok) throw new Error(await uploadRes.text());
                        const uploadData = await uploadRes.json();
                        sendToChild("sam:artifact:response", { artifactId: uploadData.uri });
                        break;
                }
            } catch (err: any) {
                console.error(`Error handling SDK message ${type}:`, err);
                sendError(err.message || "Unknown error");
            }
        },
        [appId, currentTheme, apiPrefix]
    );

    useEffect(() => {
        window.addEventListener("message", handleMessage);
        return () => window.removeEventListener("message", handleMessage);
    }, [handleMessage]);

    useEffect(() => {
        const iframes = document.querySelectorAll("iframe");
        iframes.forEach(iframe => {
            if (iframe.contentWindow) {
                iframe.contentWindow.postMessage(
                    {
                        type: "sam:theme:changed",
                        id: "theme-update",
                        payload: { theme: currentTheme },
                    },
                    "*"
                );
            }
        });
    }, [currentTheme]);
}
