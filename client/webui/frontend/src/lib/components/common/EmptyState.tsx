import type { VariantProps } from "class-variance-authority";
import { Button } from "@/lib/components/ui/button";
import type { buttonVariants } from "@/lib/components/ui/button";
import type { ReactElement } from "react";
import NotFoundIllustration from "@/assets/illustrations/NotFoundIllustration";
import ErrorIllustration from "@/assets/illustrations/ErrorIllustration";

type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];

export interface ButtonWithCallback {
    text: string;
    variant: ButtonVariant;
    onClick: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
}

interface EmptyStateProps {
    title: string;
    subtitle?: string;
    variant?: "error" | "not-found";
    image?: ReactElement;
    buttons?: ButtonWithCallback[];
}

function EmptyState({ title, subtitle, image, variant = "error", buttons }: EmptyStateProps) {
    return (
        <div className="flex h-full w-full flex-col items-center justify-center gap-3">
            {image ? image : variant === "error" ? <ErrorIllustration width={150} height={150} /> : <NotFoundIllustration width={150} height={150} />}

            <p className="text-2xl">{title}</p>
            {subtitle ? <p className="text-base">{subtitle}</p> : null}

            <div className="flex gap-2">
                {buttons &&
                    buttons.map(({ text, variant, onClick }, index) => (
                        <Button key={`button-${text}-${index}`} testid={text} title={text} variant={variant} onClick={onClick}>
                            {text}
                        </Button>
                    ))}
            </div>
        </div>
    );
}

export { EmptyState };
