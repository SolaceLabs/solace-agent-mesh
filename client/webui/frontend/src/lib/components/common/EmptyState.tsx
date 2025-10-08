import type { VariantProps } from "class-variance-authority";
import { Button } from "@/lib/components/ui/button";
import type { buttonVariants } from "@/lib/components/ui/button";
import { ErrorDisplay } from "@/assets/illustrations/ErrorDisplay";

type ButtonVariant = VariantProps<typeof buttonVariants>["variant"];

export interface ButtonWithCallback {
    text: string;
    variant: ButtonVariant;
    onClick: (event: React.MouseEvent<HTMLButtonElement, MouseEvent>) => void;
}

interface EmptyStateProps {
    title: string;
    subtitle?: string;
    buttons?: ButtonWithCallback[];
}

function EmptyState({ title, subtitle, buttons }: EmptyStateProps) {
    return (
        <div className="flex h-screen w-screen flex-col items-center justify-center gap-3">
            <ErrorDisplay width={150} height={150} />

            <p className="text-2xl">{title}</p>
            {subtitle ? <p className="text-base">{subtitle}</p> : null}

            <div className="flex gap-2">
                {buttons &&
                    buttons.map(({ text, variant, onClick }) => (
                        <Button variant={variant} onClick={onClick}>
                            {text}
                        </Button>
                    ))}
            </div>
        </div>
    );
}

export { EmptyState };
