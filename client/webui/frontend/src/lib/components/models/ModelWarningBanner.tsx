import { useNavigate } from "react-router-dom";
import { useBooleanFlagDetails } from "@openfeature/react-sdk";

import { useModelConfigStatus } from "@/lib/api/models";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { Button } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";

export function ModelWarningBanner() {
    const navigate = useNavigate();
    const { value: modelConfigUiEnabled } = useBooleanFlagDetails("model_config_ui", false);
    const { hasModelConfigWrite } = useChatContext();
    const { data: modelConfigStatus } = useModelConfigStatus();
    const showWarning = modelConfigUiEnabled && modelConfigStatus && !modelConfigStatus.configured;

    if (!showWarning) return null;

    return (
        <MessageBanner
            variant="warning"
            style={{ alignItems: "center" }}
            message={
                <div className="flex w-full items-center justify-between gap-3">
                    <span>
                        No model has been set up. Some features may not work as intended without a configured model.
                        {hasModelConfigWrite ? " Go to Agent Mesh to configure your models." : " Ask your administrator to configure models in Agent Mesh."}
                    </span>
                    {hasModelConfigWrite && (
                        <Button variant="outline" size="sm" className="shrink-0" onClick={() => navigate("/agents?tab=models")}>
                            Go to Models
                        </Button>
                    )}
                </div>
            }
        />
    );
}
