import React, { useState } from "react";
import { Copy, Check } from "lucide-react";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    Button
} from "@/lib/components/ui";

interface PastedTextDialogProps {
    isOpen: boolean;
    onClose: () => void;
    content: string;
    title?: string;
}

export const PastedTextDialog: React.FC<PastedTextDialogProps> = ({
    isOpen,
    onClose,
    content,
    title = "Pasted Text Content"
}) => {
    const [copied, setCopied] = useState(false);

    const handleCopyContent = async () => {
        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy text:", err);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col" showCloseButton>
                <DialogHeader>
                    <DialogTitle className="flex items-center justify-between gap-2">
                        <span>{title}</span>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleCopyContent}
                            tooltip={copied ? "Copied!" : "Copy to clipboard"}
                            className="h-8 w-8"
                        >
                            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                        </Button>
                    </DialogTitle>
                    <DialogDescription>
                        {content.length} characters, {content.split('\n').length} lines
                    </DialogDescription>
                </DialogHeader>
                
                <div className="flex-1 overflow-auto rounded-md border bg-muted/30 p-4">
                    <pre className="text-sm whitespace-pre-wrap break-words font-mono">
                        {content}
                    </pre>
                </div>
            </DialogContent>
        </Dialog>
    );
};