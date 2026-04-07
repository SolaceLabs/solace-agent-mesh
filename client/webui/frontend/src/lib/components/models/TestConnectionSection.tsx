import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2 } from "lucide-react";

import { Button, Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { testModelConnection } from "@/lib/api/models/service";
import { buildModelPayload } from "./modelProviderUtils";
import type { ModelFormData } from "./modelProviderUtils";

interface TestConnectionSectionProps {
    getFormData: () => ModelFormData;
    getDirtyFields?: () => Partial<Record<string, boolean>>;
    isNew: boolean;
    modelId?: string;
    disabled?: boolean;
}

export const TestConnectionSection = ({ getFormData, getDirtyFields, isNew, modelId, disabled }: TestConnectionSectionProps) => {
    const [isTesting, setIsTesting] = useState(false);
    const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
    const resultRef = useRef<HTMLDivElement>(null);

    // Scroll result banner into view when it appears
    useEffect(() => {
        if (result && resultRef.current) {
            resultRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [result]);

    const handleTestConnection = useCallback(async () => {
        setIsTesting(true);
        setResult(null);

        try {
            const formData = getFormData();
            const dirtyFields = getDirtyFields?.();
            const payload = buildModelPayload(formData, dirtyFields);

            const testPayload = {
                provider: payload.provider,
                modelName: payload.modelName,
                apiBase: payload.apiBase || undefined,
                authConfig: payload.authConfig,
                modelParams: payload.modelParams,
                // For editing, include modelId so backend can use stored credentials as fallback
                ...(!isNew && modelId ? { modelId } : {}),
            };

            const response = await testModelConnection(testPayload);
            setResult(response);
        } catch (error) {
            const message = error instanceof Error ? error.message : "An unknown error occurred while testing the connection.";
            setResult({ success: false, message });
        } finally {
            setIsTesting(false);
        }
    }, [getFormData, getDirtyFields, isNew, modelId]);

    return (
        <div className="pt-4">
            <div className="flex items-center gap-3">
                <Tooltip>
                    <TooltipTrigger asChild>
                        <span>
                            <Button type="button" variant="outline" onClick={handleTestConnection} disabled={isTesting || disabled}>
                                Test Connection
                            </Button>
                        </span>
                    </TooltipTrigger>
                    {disabled && <TooltipContent>Required configuration is missing</TooltipContent>}
                </Tooltip>
                {isTesting && (
                    <div className="flex items-center gap-2 text-sm text-(--secondary-text-wMain)">
                        <Loader2 className="size-4 animate-spin" />
                        <span>Testing connection...</span>
                    </div>
                )}
            </div>

            {result && (
                <div ref={resultRef} className="mt-3">
                    <MessageBanner variant={result.success ? "success" : "error"} message={result.message} dismissible onDismiss={() => setResult(null)} />
                </div>
            )}
        </div>
    );
};
