import { X, ExternalLink } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { useLocalStorage } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export interface OnboardingBannerProps {
    storageKey: string;
    header: string;
    description: string;
    learnMoreText: string;
    learnMoreUrl: string;
    className?: string;
}

export const OnboardingBanner = ({ storageKey, header, description, learnMoreText, learnMoreUrl, className }: OnboardingBannerProps) => {
    const [isDismissed, setIsDismissed] = useLocalStorage(storageKey, false);

    const handleDismiss = () => {
        setIsDismissed(true);
    };

    if (isDismissed) {
        return null;
    }

    return (
        <div className={cn("relative rounded-lg border border-(--learning-w20) bg-(--learning-w10) p-4", className)}>
            <Button variant="ghost" size="icon" onClick={handleDismiss} tooltip="Close" className="absolute top-2 right-2">
                <X size={16} />
            </Button>

            <div className="pr-8">
                <p className="text-sm">
                    <span className="font-semibold">{header}</span> {description}
                </p>

                <Button variant="link" onClick={() => window.open(learnMoreUrl, "_blank")} className="mt-1 !p-0">
                    {learnMoreText}
                    <ExternalLink size={14} />
                </Button>
            </div>
        </div>
    );
};
