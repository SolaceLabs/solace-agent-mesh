import type { ReactElement } from "react";
import { ExternalLink } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

interface OnboardingViewProps {
    title: string;
    description: string;
    learnMoreText?: string;
    learnMoreHref?: string;
    image?: ReactElement;
    className?: string;
    actionButtonText?: string;
    onActionClick?: () => void;
    actionButtonDisabled?: boolean;
}

function OnboardingView({ title, description, learnMoreText, learnMoreHref = "#", image, className, actionButtonText, onActionClick, actionButtonDisabled = false }: OnboardingViewProps) {
    return (
        <div className={cn("flex h-full justify-center overflow-auto p-12", className)}>
            <div className="my-auto flex max-w-6xl gap-8">
                <div className={cn("flex flex-col justify-center", !image && "max-w-2xl flex-1 items-center text-center")}>
                    <h2 className="mb-4 text-xl font-semibold">{title}</h2>
                    <p className="mb-6 text-sm text-(--secondary-text-wMain)">{description}</p>

                    {actionButtonText && (
                        <div className={cn("mb-2 flex gap-3", !image && "flex-col items-center")}>
                            <Button disabled={actionButtonDisabled} onClick={onActionClick}>
                                <span className="mr-2">+</span> {actionButtonText}
                            </Button>
                        </div>
                    )}

                    {learnMoreText && (
                        <Button variant="link" onClick={() => window.open(learnMoreHref, "_blank")} className="w-fit p-0!">
                            {learnMoreText}
                            {image && <ExternalLink size={14} />}
                        </Button>
                    )}
                </div>

                {image && <div className="flex flex-1 items-center justify-center">{image}</div>}
            </div>
        </div>
    );
}

export { OnboardingView };
