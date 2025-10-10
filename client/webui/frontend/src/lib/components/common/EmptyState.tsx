import type { VariantProps } from "class-variance-authority";
import { Button } from "@/lib/components/ui/button";
import type { buttonVariants } from "@/lib/components/ui/button";
import type { ReactElement } from "react";
import { ErrorIllustration, NotFoundIllustration } from "@/lib/assets";

type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];

export interface ButtonWithCallback {
    text: string;
    variant: ButtonVariant;
    onClick: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
}

interface EmptyStateProps {
    title: string;
    subtitle?: string;
    variant?: "error" | "notFound" | "noImage";
    image?: ReactElement;
    buttons?: ButtonWithCallback[];
}

function EmptyState({ title, subtitle, image, variant = "error", buttons }: EmptyStateProps) {
    const illustrations = {
        error: <ErrorIllustration width={150} height={150} />,
        notFound: <NotFoundIllustration width={150} height={150} />,
        noImage: null,
    };

    return (
        <div className="flex h-full w-full flex-col items-center justify-center gap-3">
            {image || illustrations[variant] || null}

            <p className="text-lg">{title}</p>
            {subtitle ? <p className="text-sm">{subtitle}</p> : null}

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
