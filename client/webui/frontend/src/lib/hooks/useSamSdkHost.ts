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

                    case "sam:agent:list":
                        // Fetch the list of available agents from the backend
                        const agentListRes = await authenticatedFetch(`${apiPrefix}/agentCards`, {
                            method: "GET",
                            headers: { "Content-Type": "application/json" },
                        });

                        if (!agentListRes.ok) {
                            throw new Error(`Failed to fetch agent list: ${await agentListRes.text()}`);
                        }

                        const agentCards = await agentListRes.json();

                        // Transform AgentCards to AgentInfo format expected by SDK
                        const agents = agentCards.map((card: any) => ({
                            id: card.name, // Use agent name as ID
                            name: card.name,
                            description: card.description || undefined,
                            version: card.version || undefined,
                            capabilities: card.capabilities || undefined,
                        }));

                        sendToChild("sam:agent:list:response", { agents });
                        break;

                    case "sam:agent:call":
                        // 1. Construct the A2A Message
                        const { agentName, prompt, context, files, sessionId: explicitSessionId } = payload;

                        // Process uploaded files into FileParts
                        const fileParts: any[] = [];
                        // Start with explicit session ID if provided (explicit control)
                        let effectiveSessionId: string | undefined = explicitSessionId;

                        if (files && files.length > 0) {
                            for (const fileData of files) {
                                try {
                                    // Decode base64 back to File object
                                    const byteCharacters = atob(fileData.data.split(',')[1]);
                                    const byteNumbers = new Array(byteCharacters.length);
                                    for (let i = 0; i < byteCharacters.length; i++) {
                                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                                    }
                                    const byteArray = new Uint8Array(byteNumbers);
                                    const blob = new Blob([byteArray], { type: fileData.type });
                                    const file = new File([blob], fileData.name, { type: fileData.type });

                                    // ALWAYS upload files to artifacts for agent calls
                                    // This ensures metadata is properly created and the agent can access the file
                                    const formData = new FormData();
                                    formData.append("upload_file", file);
                                    formData.append("filename", file.name);

                                    // Pass session ID if we have one from a previous upload
                                    if (effectiveSessionId) {
                                        formData.append("sessionId", effectiveSessionId);
                                    }

                                    const uploadRes = await authenticatedFetch("/api/v1/artifacts/upload", {
                                        method: "POST",
                                        body: formData,
                                    });

                                    if (!uploadRes.ok) {
                                        throw new Error(`Failed to upload ${file.name}: ${await uploadRes.text()}`);
                                    }

                                    const uploadData = await uploadRes.json();

                                    // Store the session ID from the first upload
                                    if (!effectiveSessionId && uploadData.sessionId) {
                                        effectiveSessionId = uploadData.sessionId;
                                    }

                                    fileParts.push({
                                        kind: "file",
                                        file: {
                                            uri: uploadData.uri,
                                            name: file.name,
                                            mimeType: file.type
                                        }
                                    });
                                } catch (error: any) {
                                    console.error(`Error processing file ${fileData.name}:`, error);
                                    sendError(`File upload failed: ${error.message}`);
                                    return; // Abort agent call on file upload failure
                                }
                            }
                        }

                        // Construct message with text and file parts
                        const messageParts: any[] = [];
                        if (prompt) {
                            messageParts.push({ kind: "text", text: prompt });
                        }
                        messageParts.push(...fileParts);

                        const a2aMessage: Message = {
                            role: "user",
                            parts: messageParts,
                            messageId: `msg-${v4()}`,
                            kind: "message",
                            contextId: effectiveSessionId, // Use session ID from file uploads
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
                        const task = initData.result;
                        const taskId = task?.id;
                        const responseSessionId = task?.contextId; // Session ID from backend

                        if (!taskId) throw new Error("Failed to start agent task");

                        // Update effectiveSessionId from task if backend created/used a session
                        if (responseSessionId && !effectiveSessionId) {
                            effectiveSessionId = responseSessionId;
                        }

                        // 3. Subscribe to SSE for this Task
                        const token = getAccessToken();
                        const sseUrl = `${apiPrefix}/sse/subscribe/${taskId}${token ? `?token=${token}` : ""}`;
                        const eventSource = new EventSource(sseUrl, { withCredentials: true });
                        
                        activeConnections.current.set(id, eventSource);

                        let accumulatedText = "";
                        const accumulatedArtifacts: any[] = [];

                        eventSource.addEventListener("status_update", (e) => {
                            try {
                                const data = JSON.parse(e.data) as SendStreamingMessageSuccessResponse;
                                const result = data.result as TaskStatusUpdateEvent;
                                
                                if (result.status?.message?.parts) {
                                    for (const part of result.status.message.parts) {
                                        const partAny = part as any; // Allow for artifact and file kinds

                                        // Handle Text Streaming
                                        if (part.kind === "text" && part.text) {
                                            sendToChild("sam:agent:stream", { text: part.text });
                                            accumulatedText += part.text;
                                        }

                                        // Handle Files (artifact_return creates file parts)
                                        if (part.kind === "file" && part.file) {
                                            console.log('File part received (artifact_return):', part.file.name, part.file);
                                            const artifactPayload = {
                                                name: part.file.name,
                                                file: part.file
                                            };
                                            sendToChild("sam:agent:artifact", artifactPayload);

                                            // Accumulate artifact object (not just URI)
                                            // This ensures artifacts with embedded bytes are also captured
                                            accumulatedArtifacts.push(artifactPayload);
                                        }

                                        // Handle Artifacts (legacy - for artifact parts with status)
                                        if (partAny.kind === "artifact" && partAny.status === "completed") {
                                            console.log('Artifact part received (legacy):', partAny.name, partAny);
                                            const artifactPayload = {
                                                name: partAny.name,
                                                file: partAny.file
                                            };
                                            sendToChild("sam:agent:artifact", artifactPayload);

                                            // Accumulate artifact object (not just URI)
                                            accumulatedArtifacts.push(artifactPayload);
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

                        eventSource.addEventListener("artifact_update", (e) => {
                            try {
                                const data = JSON.parse(e.data) as SendStreamingMessageSuccessResponse;
                                const result = data.result as TaskStatusUpdateEvent;

                                if (result.status?.message?.parts) {
                                    for (const part of result.status.message.parts) {
                                        const partAny = part as any;

                                        // Handle Artifacts from artifact_update events
                                        if (partAny.kind === "artifact") {
                                            console.log('Artifact update event received:', partAny.name, partAny.status, partAny);

                                            if (partAny.status === "completed") {
                                                const artifactPayload = {
                                                    name: partAny.name,
                                                    file: partAny.file
                                                };
                                                sendToChild("sam:agent:artifact", artifactPayload);

                                                // Accumulate artifact object (not just URI)
                                                accumulatedArtifacts.push(artifactPayload);
                                            }
                                        }
                                    }
                                }
                            } catch (err) {
                                console.error("Error parsing artifact_update SSE", err);
                            }
                        });

                        eventSource.addEventListener("final_response", () => {
                            // Task Complete
                            sendToChild("sam:agent:response", {
                                response: accumulatedText,
                                sessionId: effectiveSessionId, // Return session ID for persistent mode
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
                        // Strip data URL prefix (e.g., "data:image/png;base64,") before decoding
                        const base64Data = payload.data.includes(',') ? payload.data.split(',')[1] : payload.data;
                        const byteCharacters = atob(base64Data);
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

                        // Pass session ID if provided (for session continuity)
                        if (payload.sessionId) {
                            formData.append("sessionId", payload.sessionId);
                        }

                        const uploadRes = await authenticatedFetch("/api/v1/artifacts/upload", {
                            method: "POST",
                            body: formData,
                        });

                        if (!uploadRes.ok) throw new Error(await uploadRes.text());
                        const uploadData = await uploadRes.json();
                        sendToChild("sam:artifact:response", {
                            artifactId: uploadData.uri,
                            sessionId: uploadData.sessionId,
                            filename: uploadData.filename,
                            size: uploadData.size,
                            mimeType: uploadData.mimeType,
                            metadata: uploadData.metadata,
                            createdAt: uploadData.createdAt
                        });
                        break;

                    case "sam:artifact:download":
                        // Download artifact from backend using the by-uri endpoint
                        // The artifactId is an artifact:// URI that needs to be resolved
                        const artifactUri = payload.artifactId;

                        // Use the /artifacts/by-uri endpoint to resolve the artifact:// URI
                        const downloadUrl = `/api/v1/artifacts/by-uri?uri=${encodeURIComponent(artifactUri)}`;
                        const downloadRes = await authenticatedFetch(downloadUrl, {
                            method: "GET",
                        });

                        if (!downloadRes.ok) throw new Error(`Failed to download artifact: ${await downloadRes.text()}`);

                        // Convert blob to base64 data URL for transfer back to iframe
                        const artifactBlob = await downloadRes.blob();
                        const reader = new FileReader();
                        reader.onloadend = () => {
                            sendToChild("sam:artifact:response", {
                                data: reader.result // Base64 data URL
                            });
                        };
                        reader.onerror = () => {
                            sendError("Failed to read artifact blob");
                        };
                        reader.readAsDataURL(artifactBlob);
                        break;

                    default:
                        console.error(`[SAM SDK Host] Unhandled message type: ${type}`, { id, payload });
                        sendError(`Unhandled message type: ${type}`);
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
