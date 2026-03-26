import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { MessageBanner } from "@/lib/components/common";
import type { TestConnectionResponse } from "@/lib/api/models/service";

interface TestConnectionSectionProps {
    onTestConnection: () => void;
    isTestingConnection?: boolean;
    testConnectionResult?: TestConnectionResponse | null;
    onDismissTestResult?: () => void;
    disabled?: boolean;
}

export const TestConnectionSection = ({ onTestConnection, isTestingConnection, testConnectionResult, onDismissTestResult, disabled }: TestConnectionSectionProps) => {
    const resultRef = useRef<HTMLDivElement>(null);

    // Scroll result banner into view when it appears
    useEffect(() => {
        if (testConnectionResult && resultRef.current) {
            resultRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [testConnectionResult]);

    return (
        <div className="border-t pt-4">
            <div className="flex items-center gap-3">
                <Button type="button" variant="outline" onClick={onTestConnection} disabled={isTestingConnection || disabled}>
                    Test Connection
                </Button>
                {isTestingConnection && (
                    <div className="flex items-center gap-2 text-sm text-(--secondary-text-wMain)">
                        <Loader2 className="size-4 animate-spin" />
                        <span>Testing connection...</span>
                    </div>
                )}
            </div>

            {testConnectionResult && (
                <div ref={resultRef} className="mt-3">
                    <MessageBanner variant={testConnectionResult.success ? "success" : "error"} message={testConnectionResult.message} dismissible onDismiss={onDismissTestResult} />
                </div>
            )}
        </div>
    );
};
