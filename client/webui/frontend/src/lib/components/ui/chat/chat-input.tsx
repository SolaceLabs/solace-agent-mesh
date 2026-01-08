import * as React from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/lib/components/ui";

type ChatInputProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const ChatInput = React.forwardRef<HTMLTextAreaElement, ChatInputProps>(({ className, ...props }, ref) => (
    <Textarea
        autoComplete="off"
        ref={ref}
        name="message"
        data-testid="chat-input"
        className={cn(`bg-card flex w-full items-center rounded-md px-4 py-3 placeholder:text-[var(--color-secondary-wMain)] disabled:cursor-not-allowed disabled:opacity-50`, className)}
        {...props}
    />
));
ChatInput.displayName = "ChatInput";

export { ChatInput };
