import React, { useState } from "react";
import type { ReactNode } from "react";

import { AlertCircle } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MessageBanner, ViewWorkflowButton } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";
import type { MessageFE } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";

import { FileAttachmentMessage, FileMessage } from "./file/FileMessage";
import { ContentRenderer } from "./preview/ContentRenderer";
import { extractEmbeddedContent } from "./preview/contentUtils";
import type { ExtractedContent } from "./preview/contentUtils";

const MessageContent: React.FC<{ message: MessageFE }> = ({ message }) => {
    const [renderError, setRenderError] = useState<string | null>(null);
    if (message.isStatusBubble) {
        return null;
    }
    if (message.isUser) {
        return <span>{message.text || ""}</span>;
    }
    const trimmedText = message.text?.trim();
    if (!trimmedText) return null;
    if (message.isError) {
        return (
            <div className="flex items-center">
                <AlertCircle className="mr-2 self-start text-[var(--color-error-wMain)]" />
                <MarkdownHTMLConverter>{trimmedText}</MarkdownHTMLConverter>
            </div>
        );
    }

    const embeddedContent = extractEmbeddedContent(trimmedText);
    if (embeddedContent.length === 0) {
        return <MarkdownHTMLConverter>{trimmedText}</MarkdownHTMLConverter>;
    }

    let modifiedText = trimmedText;
    const contentElements: ReactNode[] = [];
    // Process each embedded content item
    embeddedContent.forEach((item: ExtractedContent, index: number) => {
        modifiedText = modifiedText.replace(item.originalMatch, "");

        contentElements.push(
            <div key={`embedded-${index}`} className="my-2 h-auto w-md max-w-md overflow-hidden">
                <ContentRenderer content={item.content} rendererType={item.type} mime_type={item.mimeType} setRenderError={setRenderError} />
            </div>
        );
    });

    return (
        <div>
            {renderError && <MessageBanner variant="error" message="Error rendering preview" />}
            <MarkdownHTMLConverter>{modifiedText}</MarkdownHTMLConverter>
            {contentElements}
        </div>
    );
};

const MessageWrapper: React.FC<{ message: MessageFE; children: ReactNode; className?: string }> = ({ message, children, className }) => {
    return <div className={`mt-1 space-y-1 ${message.isUser ? "ml-auto" : "mr-auto"} ${className}`}>{children}</div>;
};

const getUploadedFiles = (message: MessageFE) => {
    if (message.uploadedFiles && message.uploadedFiles.length > 0) {
        return (
            <MessageWrapper message={message} className="flex flex-wrap justify-end gap-2">
                {message.uploadedFiles.map((file, fileIdx) => (
                    <FileMessage key={`uploaded-${message.metadata?.messageId}-${fileIdx}`} filename={file.name} />
                ))}
            </MessageWrapper>
        );
    }
    return null;
};

const getFileAttachments = (message: MessageFE) => {
    if (message.files && message.files.length > 0) {
        return (
            <MessageWrapper message={message}>
                {message.files.map((file, fileIdx) => (
                    <FileAttachmentMessage key={`file-${message.metadata?.messageId}-${fileIdx}`} fileAttachment={file} />
                ))}
            </MessageWrapper>
        );
    }
    return null;
};

const getChatBubble = (message: MessageFE, chatContext: ChatContextValue, isLastWithTaskId?: boolean) => {
    const { openSidePanelTab, setTaskIdInSidePanel } = chatContext;

    if (message.isStatusBubble) {
        return null;
    }

    if (message.text) {
        const variant = message.isUser ? "sent" : "received";
        const showWorkflowButton = !message.isUser && message.isComplete && !!message.taskId && isLastWithTaskId;
        const handleViewWorkflowClick = () => {
            if (message.taskId) {
                setTaskIdInSidePanel(message.taskId);
                openSidePanelTab("workflow");
            }
        };

        return (
            <ChatBubble key={message.metadata?.messageId} variant={variant}>
                <ChatBubbleMessage variant={variant}>
                    <MessageContent message={message} />
                    {showWorkflowButton && (
                        <div className="mt-3">
                            <ViewWorkflowButton onClick={handleViewWorkflowClick} />
                        </div>
                    )}
                </ChatBubbleMessage>
            </ChatBubble>
        );
    }
    return null;
};
export const ChatMessage: React.FC<{ message: MessageFE; isLastWithTaskId?: boolean }> = ({ message, isLastWithTaskId }) => {
    const chatContext = useChatContext();
    if (!message) {
        return null;
    }
    return (
        <>
            {getChatBubble(message, chatContext, isLastWithTaskId)}
            {getUploadedFiles(message)}
            {getFileAttachments(message)}
        </>
    );
};
