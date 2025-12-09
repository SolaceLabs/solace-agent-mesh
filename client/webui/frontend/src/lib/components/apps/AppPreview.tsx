import { useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { useSamSdkHost } from "@/lib/hooks";

interface AppPreviewProps {
    appId: string;
}

export function AppPreview({ appId }: AppPreviewProps) {
    const [error, setError] = useState<string | null>(null);
    const [key, setKey] = useState(0);

    // Enable SAM SDK host communication
    useSamSdkHost(appId);

    const handleRefresh = () => {
        setKey(prev => prev + 1);
        setError(null);
    };

    const handleIframeError = () => {
        setError("App not built yet - ask agent to make changes");
    };

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
                        Refresh to see changes
                    </p>
                </div>
                <button
                    onClick={handleRefresh}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs bg-secondary hover:bg-secondary/80 rounded-md transition-colors"
                    title="Refresh preview"
                >
                    <RefreshCw className="size-3" />
                    Refresh
                </button>
            </div>
            <div className="flex-1 bg-white overflow-hidden">
                <iframe
                    key={key}
                    src={`/api/v1/apps/preview/${appId}/`}
                    className="w-full h-full border-0"
                    title="App Preview"
                    sandbox="allow-scripts allow-forms allow-popups"
                    onError={handleIframeError}
                />
            </div>
        </div>
    );
}
