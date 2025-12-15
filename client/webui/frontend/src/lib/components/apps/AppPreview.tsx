import { useState, useEffect, useRef } from "react";
import { AlertCircle, RefreshCw, ClipboardCopy, Check } from "lucide-react";
import { useSamSdkHost, useChatContext } from "@/lib/hooks";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";

interface AppPreviewProps {
    appId: string;
}

export function AppPreview({ appId }: AppPreviewProps) {
    const [error, setError] = useState<string | null>(null);
    const [isNotBuilt, setIsNotBuilt] = useState<boolean>(false);
    const [key, setKey] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isCopying, setIsCopying] = useState(false);
    const [justCopied, setJustCopied] = useState(false);
    const iframeRef = useRef<HTMLIFrameElement>(null);

    const { autoRefreshEnabled, setAutoRefreshEnabled, triggerPreviewRefresh, addNotification } = useChatContext();

    // Enable SAM SDK host communication
    useSamSdkHost(appId);

    // Check if the app is built on mount and when refreshing
    useEffect(() => {
        checkIfAppIsBuilt();
    }, [appId, key]);

    const checkIfAppIsBuilt = async () => {
        try {
            const response = await fetch(`/api/v1/apps/preview/${appId}/`, { method: 'HEAD' });
            if (response.status === 404) {
                setIsNotBuilt(true);
                setError(null);
            } else if (!response.ok) {
                setError(`Failed to load preview: ${response.statusText}`);
                setIsNotBuilt(false);
            } else {
                setIsNotBuilt(false);
                setError(null);
            }
        } catch (err) {
            // Network error or other issue
            setError(`Failed to check app status: ${err instanceof Error ? err.message : 'Unknown error'}`);
            setIsNotBuilt(false);
        }
    };

    // Auto-refresh when triggered by task completion
    useEffect(() => {
        if (triggerPreviewRefresh > 0) {
            handleRefresh();
        }
    }, [triggerPreviewRefresh]);

    const handleRefresh = () => {
        setIsRefreshing(true);
        setKey(prev => prev + 1);
        setError(null);
        setIsNotBuilt(false);

        // Reset animation after a short delay
        setTimeout(() => {
            setIsRefreshing(false);
        }, 600);
    };

    const handleIframeError = () => {
        // iframe error - check if it's because app isn't built
        checkIfAppIsBuilt();
    };

    const handleCopyLogs = async () => {
        if (!iframeRef.current?.contentWindow) {
            addNotification("Preview iframe not ready", "warning");
            return;
        }

        setIsCopying(true);

        try {
            // Request logs from the iframe via SAM SDK
            const iframe = iframeRef.current.contentWindow;

            // Get logs by calling SAM.console.getLogs() in the iframe
            const logsPromise = new Promise<any[]>((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error("Timeout")), 5000);

                const messageHandler = (event: MessageEvent) => {
                    if (event.data?.type === "sam:console:response") {
                        clearTimeout(timeout);
                        window.removeEventListener("message", messageHandler);
                        resolve(event.data.payload.logs || []);
                    }
                };

                window.addEventListener("message", messageHandler);

                // Send request to iframe
                iframe.postMessage(
                    { type: "sam:console:get-logs", id: Date.now().toString() },
                    "*"
                );
            });

            const logs = await logsPromise;

            if (!logs || logs.length === 0) {
                addNotification("No console logs captured yet", "info");
                return;
            }

            // Format logs as readable text
            const formattedLogs = logs
                .map((log) => {
                    const time = new Date(log.timestamp).toLocaleTimeString();
                    return `[${time}] [${log.level.toUpperCase()}] ${log.message}`;
                })
                .join("\n");

            // Copy to clipboard
            await navigator.clipboard.writeText(formattedLogs);

            setJustCopied(true);
            addNotification(`${logs.length} console log${logs.length !== 1 ? "s" : ""} copied to clipboard`, "success");

            // Reset the "just copied" state after 2 seconds
            setTimeout(() => setJustCopied(false), 2000);
        } catch (error) {
            console.error("Failed to copy logs:", error);
            addNotification(
                error instanceof Error ? error.message : "Failed to retrieve console logs",
                "warning"
            );
        } finally {
            setIsCopying(false);
        }
    };

    // Show placeholder when app isn't built yet
    if (isNotBuilt) {
        return (
            <div className="h-full w-full flex flex-col bg-muted/50">
                <div className="px-4 py-3 border-b bg-background flex items-center justify-between">
                    <div>
                        <h3 className="font-semibold">Preview</h3>
                        <p className="text-xs text-muted-foreground">
                            Waiting for first build
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="h-8"
                        >
                            <RefreshCw className={`size-3 mr-1.5 ${isRefreshing ? "animate-spin" : ""}`} />
                            Refresh
                        </Button>
                    </div>
                </div>
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                    <div className="text-6xl mb-4">🏗️</div>
                    <h2 className="text-2xl font-semibold mb-2">App Not Built Yet</h2>
                    <p className="text-muted-foreground max-w-md mb-6">
                        Your app is being built by the App Agent. Once the first build completes,
                        click the Refresh button above to see your app.
                    </p>
                    <div className="text-sm text-muted-foreground">
                        ← Watch the chat on the left for build progress
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full w-full flex items-center justify-center bg-muted/50">
                <div className="text-center">
                    <AlertCircle className="size-8 text-destructive mx-auto mb-2" />
                    <div className="text-sm font-semibold">Preview Error</div>
                    <div className="text-xs text-muted-foreground mt-1">{error}</div>
                    <button
                        onClick={handleRefresh}
                        className="mt-4 px-4 py-2 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full w-full flex flex-col bg-muted/50">
            <div className="px-4 py-3 border-b bg-background flex items-center justify-between">
                <div>
                    <h3 className="font-semibold">Preview</h3>
                    <p className="text-xs text-muted-foreground">
                        {autoRefreshEnabled ? "Auto-refreshes on build" : "Manual refresh required"}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                        <Switch
                            checked={autoRefreshEnabled}
                            onCheckedChange={setAutoRefreshEnabled}
                        />
                        <span className="text-xs text-muted-foreground select-none">
                            Auto-refresh
                        </span>
                    </div>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleCopyLogs}
                        disabled={isCopying}
                        className="h-8"
                        tooltip="Copy console logs to clipboard"
                    >
                        {justCopied ? (
                            <Check className="size-3 mr-1.5" />
                        ) : (
                            <ClipboardCopy className="size-3 mr-1.5" />
                        )}
                        {justCopied ? "Copied!" : "Copy Logs"}
                    </Button>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleRefresh}
                        disabled={isRefreshing}
                        className="h-8"
                    >
                        <RefreshCw className={`size-3 mr-1.5 ${isRefreshing ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </div>
            </div>
            <div className="flex-1 bg-white overflow-hidden">
                <iframe
                    ref={iframeRef}
                    key={key}
                    src={`/api/v1/apps/preview/${appId}/`}
                    className="w-full h-full border-0"
                    title="App Preview"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    onError={handleIframeError}
                />
            </div>
        </div>
    );
}
