import { useCallback, useEffect } from "react";
import { authenticatedFetch } from "@/lib/utils/api";
import { useThemeContext } from "@/lib/hooks";

export function useSamSdkHost(appId: string) {
    const { currentTheme } = useThemeContext();

    const handleMessage = useCallback(
        async (event: MessageEvent) => {
            const { type, id, payload } = event.data;
            if (!type || !type.startsWith("sam:")) return;

            const sourceWindow = event.source as Window;

            const sendResponse = (responseType: string, responsePayload: any) => {
                sourceWindow.postMessage(
                    {
                        type: responseType,
                        id,
                        payload: responsePayload,
                    },
                    { targetOrigin: "*" }
                );
            };

            const sendError = (errorMessage: string) => {
                sourceWindow.postMessage(
                    {
                        type: `${type}:error`,
                        id,
                        payload: { error: errorMessage },
                    },
                    { targetOrigin: "*" }
                );
            };

            try {
                switch (type) {
                    case "sam:init":
                        sendResponse("sam:ready", { theme: currentTheme });
                        break;

                    case "sam:theme:get":
                        sendResponse("sam:theme:response", { theme: currentTheme });
                        break;

                    case "sam:agent:call":
                        const agentResponse = await authenticatedFetch("/api/v1/agents/call", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(payload),
                        });
                        if (!agentResponse.ok) {
                            throw new Error(await agentResponse.text());
                        }
                        sendResponse("sam:agent:response", await agentResponse.json());
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
                            sendResponse("sam:storage:response", { value: null });
                        } else if (!storageRes.ok) {
                            throw new Error(await storageRes.text());
                        } else {
                            const data = await storageRes.json().catch(() => ({}));
                            sendResponse("sam:storage:response", data);
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
                        sendResponse("sam:artifact:response", { artifactId: uploadData.uri });
                        break;
                }
            } catch (err: any) {
                console.error(`Error handling SDK message ${type}:`, err);
                sendError(err.message || "Unknown error");
            }
        },
        [appId, currentTheme]
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
