import { useState, useEffect, useRef, useCallback } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import { testModelConnection } from "@/lib/api/models/service";
import { buildModelPayload } from "./modelProviderUtils";
import type { ModelFormData } from "./modelProviderUtils";

interface TestConnectionSectionProps {
    getFormData: () => ModelFormData;
    isNew: boolean;
    modelAlias?: string;
    disabled?: boolean;
}

export const TestConnectionSection = ({ getFormData, isNew, modelAlias, disabled }: TestConnectionSectionProps) => {
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
            const payload = buildModelPayload(formData);

            const testPayload = {
                provider: payload.provider,
                modelName: payload.modelName,
                apiBase: payload.apiBase || undefined,
                authType: payload.authType,
                authConfig: payload.authConfig,
                modelParams: payload.modelParams,
                // For editing, include alias so backend can use stored credentials as fallback
                ...(!isNew && modelAlias ? { alias: modelAlias } : {}),
            };

            const response = await testModelConnection(testPayload);
            setResult(response);
        } catch (error) {
            const message = error instanceof Error ? error.message : "An unknown error occurred while testing the connection.";
            setResult({ success: false, message });
        } finally {
            setIsTesting(false);
        }
    }, [getFormData, isNew, modelAlias]);

    return (
        <div className="border-t pt-4">
            <div className="flex items-center gap-3">
                <Button type="button" variant="outline" onClick={handleTestConnection} disabled={isTesting || disabled}>
                    Test Connection
                </Button>
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
