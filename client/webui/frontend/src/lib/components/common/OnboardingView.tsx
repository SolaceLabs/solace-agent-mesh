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
}

function OnboardingView({ title, description, learnMoreText, learnMoreHref = "#", image, className }: OnboardingViewProps) {
    return (
        <div className={cn("flex h-full items-center justify-center p-12", className)}>
            <div className="grid max-w-6xl grid-cols-2">
                <div className="flex flex-col justify-center">
                    <h2 className="mb-4 text-xl font-semibold">{title}</h2>
                    <p className="text-muted-foreground mb-6 text-sm">{description}</p>
                    {learnMoreText && (
                        <Button variant="link" onClick={() => window.open(learnMoreHref, "_blank")} className="w-fit p-0!">
                            {learnMoreText}
                            <ExternalLink size={14} />
                        </Button>
                    )}
                </div>

                <div className="flex items-center justify-center">{image}</div>
            </div>
        </div>
    );
}

export { OnboardingView };
