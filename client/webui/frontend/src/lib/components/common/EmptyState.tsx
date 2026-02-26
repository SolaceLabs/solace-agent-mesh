import { Button } from "@/lib/components/ui/button";
import type { ReactElement } from "react";
import { ErrorIllustration, NotFoundIllustration } from "@/lib/assets";
import { cn } from "@/lib/utils";
import { Spinner } from "../ui/spinner";
import type { ButtonVariant } from "@/lib/types/ui";

export interface ButtonWithCallback {
    icon?: ReactElement;
    text: string;
    variant: ButtonVariant;
    onClick: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
}

interface EmptyStateProps {
    title: string;
    subtitle?: string | React.ReactNode;
    variant?: "error" | "notFound" | "loading" | "noImage";
    image?: ReactElement;
    buttons?: ButtonWithCallback[];
    className?: string;
}

function EmptyState({ title, subtitle, image, variant = "error", buttons, className }: EmptyStateProps) {
    const illustrations = {
        error: <ErrorIllustration width={150} height={150} />,
        notFound: <NotFoundIllustration width={150} height={150} />,
        loading: <Spinner size="large" />,
        noImage: null,
    };

    return (
        <div className={cn("flex h-full w-full flex-col items-center justify-center gap-3", className)}>
            {image || illustrations[variant] || null}

            <p className="mt-4 text-lg">{title}</p>
            {subtitle ? <p className="max-w-xl text-center text-sm">{subtitle}</p> : null}

            <div className="mt-3 flex min-w-50 flex-col gap-2">
                {buttons &&
                    buttons.map(({ icon, text, variant, onClick }, index) => (
                        <Button key={`button-${text}-${index}`} testid={text} title={text} variant={variant} onClick={onClick}>
                            {icon ? icon : null}
                            {text}
                        </Button>
                    ))}
            </div>
        </div>
    );
}

export { EmptyState };
