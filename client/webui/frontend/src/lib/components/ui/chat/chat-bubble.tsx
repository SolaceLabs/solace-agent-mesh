import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Avatar, AvatarFallback, AvatarImage, Button } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

// ChatBubble
const chatBubbleVariant = cva("flex gap-2 max-w-full items-end relative group", {
    variants: {
        variant: {
            received: "self-start",
            sent: "self-end flex-row-reverse",
        },
        layout: {
            default: "",
            ai: "max-w-full w-full items-center",
        },
    },
    defaultVariants: {
        variant: "received",
        layout: "default",
    },
});

interface ChatBubbleProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof chatBubbleVariant> {}

const ChatBubble = React.forwardRef<HTMLDivElement, ChatBubbleProps>(({ className, variant, layout, children, ...props }, ref) => (
    <div className={cn(chatBubbleVariant({ variant, layout, className }), "group relative")} ref={ref} {...props}>
        {React.Children.map(children, child =>
            React.isValidElement(child) && typeof child.type !== "string"
                ? React.cloneElement(child, {
                      variant,
                      layout,
                  } as React.ComponentProps<typeof child.type>)
                : child
        )}
    </div>
));
ChatBubble.displayName = "ChatBubble";

// ChatBubbleAvatar
interface ChatBubbleAvatarProps {
    src?: string;
    fallback?: string;
    className?: string;
}

const ChatBubbleAvatar: React.FC<ChatBubbleAvatarProps> = ({ src, fallback, className }) => (
    <Avatar className={className}>
        <AvatarImage src={src} alt="Avatar" />
        <AvatarFallback>{fallback}</AvatarFallback>
    </Avatar>
);

// ChatBubbleMessage
const chatBubbleMessageVariants = cva("", {
    variants: {
        variant: {
            received: "rounded-r-lg rounded-tl-lg",
            sent: "rounded-l-lg rounded-tr-lg justify-end bg-[var(--message-background)] p-4",
        },
        layout: {
            default: "",
            ai: "border-t w-full rounded-none bg-transparent",
        },
    },
    defaultVariants: {
        variant: "received",
        layout: "default",
    },
});

interface ChatBubbleMessageProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof chatBubbleMessageVariants> {
    isComplete?: boolean;
}

const ChatBubbleMessage = React.forwardRef<HTMLDivElement, ChatBubbleMessageProps>(({ className, variant, layout, children, ...props }, ref) => (
    <div className={cn(chatBubbleMessageVariants({ variant, layout, className }), "relative max-w-full leading-[150%] break-words")} ref={ref} {...props}>
        <>{children}</>
    </div>
));
ChatBubbleMessage.displayName = "ChatBubbleMessage";

// ChatBubbleTimestamp
interface ChatBubbleTimestampProps extends React.HTMLAttributes<HTMLDivElement> {
    timestamp: string;
}

const ChatBubbleTimestamp: React.FC<ChatBubbleTimestampProps> = ({ timestamp, className, ...props }) => (
    <div className={cn("mt-2 text-right text-xs", className)} {...props}>
        {timestamp}
    </div>
);

// ChatBubbleAction
type ChatBubbleActionProps = React.ComponentProps<typeof Button> & {
    icon: React.ReactNode;
};

const ChatBubbleAction: React.FC<ChatBubbleActionProps> = ({ icon, onClick, className, variant = "ghost", ...props }) => (
    <Button variant={variant} className={className} onClick={onClick} {...props}>
        {icon}
    </Button>
);

interface ChatBubbleActionWrapperProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "sent" | "received";
    className?: string;
}

const ChatBubbleActionWrapper = React.forwardRef<HTMLDivElement, ChatBubbleActionWrapperProps>(({ variant, className, children, ...props }, ref) => (
    <div
        ref={ref}
        className={cn("absolute top-1/2 flex -translate-y-1/2 opacity-0 transition-opacity duration-200 group-hover:opacity-100", variant === "sent" ? "-left-1 -translate-x-full flex-row-reverse" : "-right-1 translate-x-full", className)}
        {...props}
    >
        {children}
    </div>
));
ChatBubbleActionWrapper.displayName = "ChatBubbleActionWrapper";

export { ChatBubble, ChatBubbleAvatar, ChatBubbleMessage, ChatBubbleTimestamp, ChatBubbleAction, ChatBubbleActionWrapper };
