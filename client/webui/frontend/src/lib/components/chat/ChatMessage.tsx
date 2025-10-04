import React, { useState, useRef, useEffect } from "react";
import type { ReactNode } from "react";

import { AlertCircle, FileText, ThumbsDown, ThumbsUp } from "lucide-react";

import {
    ChatBubble,
    ChatBubbleAction,
    ChatBubbleActionWrapper,
    ChatBubbleMessage,
    MarkdownHTMLConverter,
    MessageBanner,
} from "@/lib/components";
import { Button, Textarea } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactPart, FileAttachment, FilePart, MessageFE, TextPart } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";

import { ArtifactMessage, FileMessage } from "./file";
import { FeedbackModal } from "./FeedbackModal";
import { ContentRenderer } from "./preview/ContentRenderer";
import { extractEmbeddedContent } from "./preview/contentUtils";
import { decodeBase64Content } from "./preview/previewUtils";
import { downloadFile } from "@/lib/utils/download";
import type { ExtractedContent } from "./preview/contentUtils";

const RENDER_TYPES_WITH_RAW_CONTENT = ["image", "audio"];

const MessageActions: React.FC<{
    message: MessageFE;
    showWorkflowButton: boolean;
    showFeedbackActions: boolean;
    handleViewWorkflowClick: () => void;
}> = ({ message, showWorkflowButton, showFeedbackActions, handleViewWorkflowClick }) => {
    const { configCollectFeedback, submittedFeedback, handleFeedbackSubmit, addNotification } = useChatContext();
    const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState(false);
    const [feedbackType, setFeedbackType] = useState<"up" | "down" | null>(null);

    const taskId = message.taskId;
    const submittedFeedbackType = taskId ? submittedFeedback[taskId]?.type : undefined;

    const handleThumbClick = (type: "up" | "down") => {
        setFeedbackType(type);
        setIsFeedbackModalOpen(true);
    };

    const handleModalClose = () => {
        setIsFeedbackModalOpen(false);
        setFeedbackType(null);
    };

    const handleModalSubmit = async (feedbackText: string) => {
        if (!feedbackType || !taskId) return;

        try {
            await handleFeedbackSubmit(taskId, feedbackType, feedbackText);
            addNotification("Feedback submitted successfully", "success");
        } catch (error) {
            addNotification("Failed to submit feedback. Please try again.", "error");
            throw error; // Re-throw to prevent modal from closing
        }
    };

    const shouldShowFeedback = showFeedbackActions && configCollectFeedback;

    if (!showWorkflowButton && !shouldShowFeedback) {
        return null;
    }

    return (
        <>
            <div className="mt-3 space-y-2">
                <div className="flex items-center justify-start gap-2">
                    {showWorkflowButton && <ViewWorkflowButton onClick={handleViewWorkflowClick} />}
                    {shouldShowFeedback && (
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="icon"
                                className={`h-6 w-6 ${submittedFeedbackType ? "!opacity-100" : ""}`}
                                onClick={() => handleThumbClick("up")}
                                disabled={!!submittedFeedbackType}
                            >
                                <ThumbsUp
                                    className={`h-4 w-4 ${submittedFeedbackType === "up" ? "fill-yellow-500 text-yellow-500 dark:fill-yellow-500 dark:text-yellow-500 !opacity-100" : ""}`}
                                />
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className={`h-6 w-6 ${submittedFeedbackType ? "!opacity-100" : ""}`}
                                onClick={() => handleThumbClick("down")}
                                disabled={!!submittedFeedbackType}
                            >
                                <ThumbsDown
                                    className={`h-4 w-4 ${submittedFeedbackType === "down" ? "fill-yellow-500 text-yellow-500 dark:fill-yellow-500 dark:text-yellow-500 opacity-100" : ""}`}
                                />
                            </Button>
                        </div>
                    )}
                </div>
            </div>
            {feedbackType && (
                <FeedbackModal
                    isOpen={isFeedbackModalOpen}
                    onClose={handleModalClose}
                    feedbackType={feedbackType}
                    onSubmit={handleModalSubmit}
                />
            )}
        </>
    );
};

const MessageContent: React.FC<{ message: MessageFE; textContent: string }> = ({ message, textContent }) => {
    const [renderError, setRenderError] = useState<string | null>(null);

    if (message.isError) {
        return (
            <div className="flex items-center">
                <AlertCircle className="mr-2 self-start text-[var(--color-error-wMain)]" />
                <MarkdownHTMLConverter>{textContent}</MarkdownHTMLConverter>
            </div>
        );
    }

    const embeddedContent = extractEmbeddedContent(textContent);
    if (embeddedContent.length === 0) {
        return <MarkdownHTMLConverter>{textContent}</MarkdownHTMLConverter>;
    }

    let modifiedText = textContent;
    const contentElements: ReactNode[] = [];
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
                    <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} isEmbedded={true} />
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



const getChatBubble = (message: MessageFE, chatContext: ChatContextValue, isLastWithTaskId?: boolean) => {
    console.log(`[ChatMessage] Rendering bubble for message:`, message);
    const { openSidePanelTab, setTaskIdInSidePanel } = chatContext;

    if (message.isStatusBubble) {
        return null;
    }

    // Group contiguous parts to handle interleaving of text and files
    const groupedParts: (TextPart | FilePart | ArtifactPart)[] = [];
    let currentTextGroup = "";

    message.parts?.forEach(part => {
        if (part.kind === "text") {
            currentTextGroup += (part as TextPart).text;
        } else if (part.kind === "file" || part.kind === "artifact") {
            if (currentTextGroup) {
                groupedParts.push({ kind: "text", text: currentTextGroup });
                currentTextGroup = "";
            }
            groupedParts.push(part);
        }
    });
    if (currentTextGroup) {
        groupedParts.push({ kind: "text", text: currentTextGroup });
    }

    console.log(`[ChatMessage] Grouped parts for message:`, groupedParts);

    const hasContent = groupedParts.some(p => (p.kind === "text" && p.text.trim()) || p.kind === "file" || p.kind === "artifact");
    if (!hasContent) {
        return null;
    }

    const variant = message.isUser ? "sent" : "received";
    const showWorkflowButton = !message.isUser && message.isComplete && !!message.taskId && !!isLastWithTaskId;
    const showFeedbackActions = !message.isUser && message.isComplete && !!message.taskId;

    const handleViewWorkflowClick = () => {
        if (message.taskId) {
            setTaskIdInSidePanel(message.taskId);
            openSidePanelTab("workflow");
        }
    };

    // Helper function to render artifact/file parts
    const renderArtifactOrFilePart = (part: ArtifactPart | FilePart, index: number) => {
        if (part.kind === "file") {
            const filePart = part as FilePart;
            const fileInfo = filePart.file;
            const attachment: FileAttachment = {
                name: fileInfo.name || "untitled_file",
                mime_type: fileInfo.mimeType,
            };
            if ("bytes" in fileInfo && fileInfo.bytes) {
                attachment.content = fileInfo.bytes;
            } else if ("uri" in fileInfo && fileInfo.uri) {
                attachment.uri = fileInfo.uri;
            }
            return (
                <ArtifactMessage key={`part-file-${index}`} status="completed" name={attachment.name} fileAttachment={attachment} />
            );
        }
        if (part.kind === "artifact") {
            const artifactPart = part as ArtifactPart;
            switch (artifactPart.status) {
                case "completed":
                    return (
                        <ArtifactMessage key={`part-artifact-${index}`} status="completed" name={artifactPart.name} fileAttachment={artifactPart.file!} />
                    );
                case "in-progress":
                    return (
                        <ArtifactMessage key={`part-artifact-${index}`} status="in-progress" name={artifactPart.name} bytesTransferred={artifactPart.bytesTransferred!} />
                    );
                case "failed":
                    return (
                        <ArtifactMessage key={`part-artifact-${index}`} status="failed" name={artifactPart.name} error={artifactPart.error} />
                    );
                default:
                    return null;
            }
        }
        return null;
    };

    // Count text and artifact parts for workflow button logic
    const textParts = groupedParts.filter(part => part.kind === "text");
    const artifactParts = groupedParts.filter(part => part.kind === "artifact" || part.kind === "file");

    return (
        <div key={message.metadata?.messageId} className="space-y-2">
            {/* Render parts in their original order to preserve interleaving */}
            {groupedParts.map((part, index) => {
                if (part.kind === "text") {
                    const isLastTextPart = index === groupedParts.length - 1 ||
                        !groupedParts.slice(index + 1).some(p => p.kind === "text");

                    return (
                        <ChatBubble key={`part-${index}`} variant={variant}>
                            <ChatBubbleMessage variant={variant}>
                                <MessageContent message={message} textContent={(part as TextPart).text} />
                                {/* Show actions on the last text part */}
                                {isLastTextPart && (
                                    <MessageActions
                                        message={message}
                                        showWorkflowButton={showWorkflowButton}
                                        showFeedbackActions={showFeedbackActions}
                                        handleViewWorkflowClick={handleViewWorkflowClick}
                                    />
                                )}
                            </ChatBubbleMessage>
                        </ChatBubble>
                    );
                } else if (part.kind === "artifact" || part.kind === "file") {
                    return renderArtifactOrFilePart(part, index);
                }
                return null;
            })}

            {/* Show actions if no text content but artifacts are present */}
            {textParts.length === 0 && artifactParts.length > 0 && (
                <div className="flex justify-end">
                    <MessageActions
                        message={message}
                        showWorkflowButton={showWorkflowButton}
                        showFeedbackActions={showFeedbackActions}
                        handleViewWorkflowClick={handleViewWorkflowClick}
                    />
                </div>
            )}
        </div>
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
        </>
    );
};
