import React from "react";

import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, AlertTriangle, Info, CheckCircle, X } from "lucide-react";

import { Button } from "@/lib/components";
import { messageColourVariants } from "./messageColourVariants";
import { cn } from "@/lib/utils";

export const BANNER_BUTTON_STYLES = "h-min !bg-transparent p-0 font-normal text-current underline hover:!text-current/60 dark:hover:text-white";

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

/*
 * The following precedence is applied to the props:
 *
 * button > buttonText, action
 *
 * Props of lower precdence will be ignored
 * */
export interface MessageBannerBaseProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof messageBannerVariants> {
    message: string;
    icon?: React.ReactNode;
    action?: (event: React.MouseEvent<HTMLButtonElement>) => void;
    buttonText?: string;
    button?: React.ReactNode;
    dismissible?: boolean;
    onDismiss?: () => void;
}

export type MessageBannerProps = MessageBannerBaseProps;

function MessageBanner({ className, variant = "error", message, icon, button, action, buttonText, dismissible = false, onDismiss, ...props }: MessageBannerProps) {
    const IconComponent = iconMap[variant || "error"];

    return (
        <div className={cn(messageBannerVariants({ variant, className }), "items-start")} role="alert" aria-live="polite" {...props}>
            {icon || <IconComponent className="size-5 shrink-0" />}
            <span>{message}</span>

            <div className="ml-auto flex items-center gap-1">
                {button ||
                    (action && buttonText && (
                        <Button variant="link" className={BANNER_BUTTON_STYLES} onClick={action}>
                            {buttonText}
                        </Button>
                    ))}
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
