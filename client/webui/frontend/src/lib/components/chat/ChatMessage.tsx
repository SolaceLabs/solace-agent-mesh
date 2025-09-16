import React, { useState } from "react";
import type { ReactNode } from "react";

import { AlertCircle, FileText } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MessageBanner } from "@/lib/components";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { useChatContext } from "@/lib/hooks";
import type { FileAttachment, MessageFE, TextPart } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";

import { FileAttachmentMessage, FileMessage } from "./file/FileMessage";
import { ContentRenderer } from "./preview/ContentRenderer";
import { extractEmbeddedContent } from "./preview/contentUtils";
import { decodeBase64Content } from "./preview/previewUtils";
import type { ExtractedContent } from "./preview/contentUtils";

const RENDER_TYPES_WITH_RAW_CONTENT = ["image", "audio"];

const MessageContent: React.FC<{ message: MessageFE }> = ({ message }) => {
    const [renderError, setRenderError] = useState<string | null>(null);
    if (message.isStatusBubble) {
        return null;
    }

    // Derive text content from the `parts` array for both user and agent messages.
    const textParts = message.parts?.filter(p => p.kind === "text") as TextPart[] | undefined;
    const combinedText = textParts?.map(p => p.text).join("") || "";

    if (message.isUser) {
        return <span>{combinedText}</span>;
    }

    const trimmedText = combinedText.trim();
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

        if (item.type === "file") {
            const fileAttachment: FileAttachment = {
                name: item.filename || "downloaded_file",
                content: item.content,
                mime_type: item.mimeType,
            };
            contentElements.push(
                <div key={`embedded-file-${index}`} className="my-2">
                    <FileAttachmentMessage fileAttachment={fileAttachment} isEmbedded={true} />
                </div>
            );
        } else if (!RENDER_TYPES_WITH_RAW_CONTENT.includes(item.type)) {
            const finalContent = decodeBase64Content(item.content);
            if (finalContent) {
                contentElements.push(
                    <div key={`embedded-${index}`} className="my-2 h-auto w-md max-w-md">
                        <ContentRenderer content={finalContent} rendererType={item.type} mime_type={item.mimeType} setRenderError={setRenderError} />
                    </div>
                );
            }
        }
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
                    <FileMessage key={`uploaded-${message.metadata?.messageId}-${fileIdx}`} filename={file.name} mimeType={file.type} />
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

    const textContent = message.parts?.some(p => p.kind === "text" && p.text.trim());

    if (!textContent && !message.artifactNotification) {
        return null;
    }

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
                {textContent && <MessageContent message={message} />}
                {message.artifactNotification && (
                    <div className="my-1 flex items-center rounded-md bg-blue-100 p-2 dark:bg-blue-900/50">
                        <FileText className="mr-2 text-blue-500 dark:text-blue-400" />
                        <span className="text-sm">
                            Artifact created: <strong>{message.artifactNotification.name}</strong>
                            {message.artifactNotification.version && ` (v${message.artifactNotification.version})`}
                        </span>
                    </div>
                )}
                {showWorkflowButton && (
                    <div className="mt-3">
                        <ViewWorkflowButton onClick={handleViewWorkflowClick} />
                    </div>
                )}
            </ChatBubbleMessage>
        </ChatBubble>
    );
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
