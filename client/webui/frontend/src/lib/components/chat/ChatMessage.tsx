import React, { useState } from "react";
import type { ReactNode } from "react";

import { AlertCircle, FileText } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MessageBanner } from "@/lib/components";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { useChatContext } from "@/lib/hooks";
import type { FileAttachment, MessageFE, TextPart } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";
import { authenticatedFetch } from "@/lib/utils/api";

import { FileAttachmentMessage, FileMessage } from "./file/FileMessage";
import { ContentRenderer } from "./preview/ContentRenderer";
import { extractEmbeddedContent } from "./preview/contentUtils";
import { decodeBase64Content } from "./preview/previewUtils";
import type { ExtractedContent } from "./preview/contentUtils";

const RENDER_TYPES_WITH_RAW_CONTENT = ["image", "audio"];

const MessageContent: React.FC<{ message: MessageFE }> = ({ message }) => {
    const [renderError, setRenderError] = useState<string | null>(null);
    const chatContext = useChatContext();
    
    if (message.isStatusBubble) {
        return null;
    }

    // Derive text content from the `parts` array for both user and agent messages.
    const textParts = message.parts?.filter(p => p.kind === "text") as TextPart[] | undefined;
    const combinedText = textParts?.map(p => p.text).join("") || "";

    if (message.isUser) {
        return <span>{combinedText}</span>;
    }

    // Handle authentication link FIRST (before checking for empty text)
    if (message.authenticationLink) {
        const isActionTaken = message.authenticationLink.actionTaken || false;
        
        const handleAuthClick = () => {
            if (isActionTaken) return; // Prevent multiple clicks
            
            // Update the message to mark action as taken
            chatContext.setMessages((prevMessages: MessageFE[]) =>
                prevMessages.map(msg =>
                    msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink
                        ? { ...msg, authenticationLink: { ...msg.authenticationLink, actionTaken: true } }
                        : msg
                )
            );
            
            const popup = window.open(
                message.authenticationLink!.url,
                "_blank",
                "width=800,height=700,scrollbars=yes,resizable=yes"
            );
            if (popup) {
                popup.focus();
            }
        };

        const handleRejectClick = async () => {
            if (isActionTaken) return; // Prevent multiple clicks
            
            const gatewayTaskId = message.authenticationLink?.gatewayTaskId;
            if (!gatewayTaskId) {
                console.error("No gateway_task_id available for rejection");
                // Still mark action as taken to disable buttons
                chatContext.setMessages((prevMessages: MessageFE[]) =>
                    prevMessages.map(msg =>
                        msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink
                            ? { ...msg, authenticationLink: { ...msg.authenticationLink, actionTaken: true } }
                            : msg
                    )
                );
                return;
            }
            
            // Mark action as taken immediately to disable buttons
            chatContext.setMessages((prevMessages: MessageFE[]) =>
                prevMessages.map(msg =>
                    msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink
                        ? { ...msg, authenticationLink: { ...msg.authenticationLink, actionTaken: true } }
                        : msg
                )
            );
            
            try {
                const response = await authenticatedFetch(`/api/v1/tasks/${gatewayTaskId}:cancel`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "tasks/cancel",
                        params: {
                            id: gatewayTaskId,
                        },
                        id: Date.now(),
                    }),
                    credentials: "include",
                });
                
                if (response.ok) {
                    console.log("Authentication rejected successfully");
                    // The SSE handler will receive the final event and update isResponding to false
                    // No need to manually call handleCancel as that would send another cancel request
                } else {
                    console.error("Failed to reject authentication:", response.status, response.statusText);
                }
            } catch (error) {
                console.error("Error rejecting authentication:", error);
            }
        };

        const targetAgent = message.authenticationLink.targetAgent || "Agent";
        
        return (
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                    Action Needed
                </h3>
                <div className="bg-gray-50 dark:bg-gray-700 rounded-md p-3 mb-4">
                    <div className="text-sm text-gray-600 dark:text-gray-300">
                        The "{targetAgent}" requires authentication. Please click to proceed.
                    </div>
                </div>
                <div className="flex space-x-3">
                    <button
                        onClick={handleRejectClick}
                        disabled={isActionTaken}
                        className={`flex-1 px-4 py-2 text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                            isActionTaken
                                ? "text-gray-400 bg-gray-100 dark:bg-gray-700 dark:text-gray-500 border border-gray-200 dark:border-gray-600 cursor-not-allowed"
                                : "text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 focus:ring-gray-500"
                        }`}
                    >
                        {isActionTaken ? "Rejected" : "Reject"}
                    </button>
                    <button
                        onClick={handleAuthClick}
                        disabled={isActionTaken}
                        className={`flex-1 px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                            isActionTaken
                                ? "bg-gray-400 cursor-not-allowed"
                                : "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500"
                        }`}
                    >
                        {isActionTaken ? "Authentication Window Opened" : message.authenticationLink.text}
                    </button>
                </div>
            </div>
        );
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

    if (!textContent && !message.artifactNotification && !message.authenticationLink) {
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
                {!textContent && message.authenticationLink && <MessageContent message={message} />}
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
