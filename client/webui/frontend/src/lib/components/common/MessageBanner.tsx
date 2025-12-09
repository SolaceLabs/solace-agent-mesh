import React from "react";

import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, Info, CheckCircle, X } from "lucide-react";

import { Button } from "@/lib/components";
import { messageColourVariants } from "./messageColourVariants";
import { cn } from "@/lib/utils";

const messageBannerVariants = cva("flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all border-l-4 border-solid ", {
    variants: { variant: messageColourVariants },
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

export interface MessageBannerBaseProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof messageBannerVariants> {
    message: string | React.ReactNode;
    icon?: React.ReactNode;
    dismissible?: boolean;
    onDismiss?: () => void;
}

export type MessageBannerProps = MessageBannerBaseProps;

function MessageBanner({ className, variant = "error", message, icon, dismissible = false, onDismiss, ...props }: MessageBannerProps) {
    const IconComponent = iconMap[variant || "error"];

    return (
        <div data-testid="messageBanner" className={cn(messageBannerVariants({ variant, className }), "items-start")} role="alert" aria-live="polite" {...props}>
            {icon || <IconComponent className="size-5 shrink-0" />}
            {typeof message === "string" ? <span>{message}</span> : message}

            <div className="ml-auto flex items-center gap-1">
                {dismissible && onDismiss && (
                    <Button variant="link" className="h-min self-center p-0" onClick={onDismiss} aria-label="Dismiss">
                        <X className="size-3" />
                    </Button>
                )}
            </div>
        </div>
    );
}

export { MessageBanner };
