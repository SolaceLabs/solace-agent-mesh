import { useBooleanFlagDetails } from "@openfeature/react-sdk";

import { ModelWarningBanner } from "@/lib/components/models/ModelWarningBanner";
import { useChatContext } from "@/lib/hooks";
import { useModelConfigStatus } from "@/lib/api/models";
import { cn } from "@/lib/utils";

interface PageLayoutProps {
    children: React.ReactNode;
    className?: string;
}

export function PageLayout({ children, className }: PageLayoutProps) {
    const { value: modelConfigUiEnabled } = useBooleanFlagDetails("model_config_ui", false);
    const { hasModelConfigWrite } = useChatContext();
    const { data: modelConfigStatus } = useModelConfigStatus();
    const showModelWarning = modelConfigUiEnabled && modelConfigStatus && !modelConfigStatus.configured;

    return (
        <div className={cn("flex h-full w-full flex-col overflow-hidden", className)}>
            <ModelWarningBanner showWarning={!!showModelWarning} hasModelConfigWrite={hasModelConfigWrite} />
            {children}
        </div>
    );
}
