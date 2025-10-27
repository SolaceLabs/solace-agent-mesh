import React from "react";

import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, Info, CheckCircle, X } from "lucide-react";

import { Button } from "@/lib/components";
import { cn } from "@/lib/utils";

const messageBannerVariants = cva("flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all border-l-4 border-solid ", {
    variants: {
        variant: {
            error: "bg-[var(--color-error-w10)] text-[var(--color-error-wMain)] border-[var(--color-error-wMain)] dark:bg-[var(--color-error-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-error-w10)]",
            warning: "bg-[var(--color-warning-w10)] text-[var(--color-warning-wMain)] border-[var(--color-warning-wMain)] dark:bg-[var(--color-warning-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-warning-w10)]",
            info: "bg-[var(--color-info-w10)] text-[var(--color-info-wMain)] border-[var(--color-info-w10)] dark:bg-[var(--color-info-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-info-w10)]",
            success: "bg-[var(--color-success-w10)] text-[var(--color-success-wMain)] border-[var(--color-success-w10)] dark:bg-[var(--color-success-wMain)] dark:text-[var(--color-primary-text-w10)] dark:border-[var(--color-success-w10)]",
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

export interface MessageBannerProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof messageBannerVariants> {
    message: string;
    dismissible?: boolean;
    onDismiss?: () => void;
}

function MessageBanner({ className, variant = "error", message, dismissible = false, onDismiss, ...props }: MessageBannerProps) {
    const IconComponent = iconMap[variant || "error"];

    return (
        <div className={cn(messageBannerVariants({ variant, className }))} role="alert" aria-live="polite" {...props}>
            <IconComponent className="size-5 shrink-0" />
            <span className="flex-1">{message}</span>
            {dismissible && onDismiss && (
                <Button variant="ghost" onClick={onDismiss} aria-label="Dismiss">
                    <X className="size-3" />
                </Button>
            )}
        </div>
    );
}

export { MessageBanner };
