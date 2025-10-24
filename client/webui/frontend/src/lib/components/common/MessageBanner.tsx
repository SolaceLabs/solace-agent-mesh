import React from "react";

import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, Info, CheckCircle, X } from "lucide-react";

import { Button } from "@/lib/components";
import { cn } from "@/lib/utils";

const messageBannerVariants = cva("flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all border-l-4 border-solid ", {
    variants: {
        variant: {
            error: "bg-[var(--color-error-w20)] text-[var(--color-error-wMain)] border-[var(--color-error-wMain)] dark:bg-[var(--color-error-w100)]/60 dark:text-[var(--color-white)] dark:border-[var(--color-error-wMain)]",
            warning: "bg-[var(--color-warning-w10)] text-[var(--color-warning-wMain)] border-[var(--color-warning-wMain)] dark:bg-[var(--color-warning-w100)]/60 dark:text-[var(--color-white)] dark:border-[var(--color-warning-wMain)]",
            info: "bg-[var(--color-info-w20)] text-[var(--color-info-wMain)] border-[var(--color-info-wMain)] dark:bg-[var(--color-info-w100)]/60 dark:text-[var(--color-white)] dark:border-[var(--color-info-wMain)]",
            success: "bg-[var(--color-success-w20)] text-[var(--color-success-wMain)] border-[var(--color-success-w40)] dark:bg-[var(--color-success-w100)]/60 dark:text-[var(--color-white)] dark:border-l-[var(--color-success-w70)]",
        },
    },
    defaultVariants: {
        variant: "error",
    },
});

const iconMap = {
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
    success: CheckCircle,
};

type ActionProps =
    | {
          action: (event: React.MouseEvent<HTMLButtonElement>) => void;
          buttonText: string;
      }
    | {
          action?: undefined;
          buttonText?: undefined;
      };

export interface MessageBannerBaseProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof messageBannerVariants> {
    message: string;
    dismissible?: boolean;
    onDismiss?: () => void;
}

export type MessageBannerProps = MessageBannerBaseProps & ActionProps;

function MessageBanner({ className, variant = "error", message, action, buttonText, dismissible = false, onDismiss, ...props }: MessageBannerProps) {
    const IconComponent = iconMap[variant || "error"];

    return (
        <div className={cn(messageBannerVariants({ variant, className }), "items-start")} role="alert" aria-live="polite" {...props}>
            <IconComponent className="size-5 shrink-0" />
            <span>{message}</span>

            {action && buttonText && (
                <Button variant="link" className="ml-auto h-min p-0 font-normal text-current underline hover:text-current/60 dark:hover:text-white" onClick={action}>
                    {buttonText}
                </Button>
            )}
            {dismissible && onDismiss && (
                <Button variant="link" className="ml-auto h-min self-center p-0" onClick={onDismiss} aria-label="Dismiss">
                    <X className="size-3" />
                </Button>
            )}
        </div>
    );
}

export { MessageBanner };
