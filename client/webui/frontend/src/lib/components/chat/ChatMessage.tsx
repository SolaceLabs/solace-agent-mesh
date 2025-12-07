import React, { useState } from "react";
import type { ReactNode } from "react";

import { AlertCircle, ThumbsDown, ThumbsUp } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MessageBanner } from "@/lib/components";
import { Button } from "@/lib/components/ui";
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
import { AuthenticationMessage } from "./authentication/AuthenticationMessage";
import { SelectableMessageContent } from "./selection";
import { MessageHoverButtons } from "./MessageHoverButtons";

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

        await handleFeedbackSubmit(taskId, feedbackType, feedbackText);
        addNotification("Feedback submitted successfully", "success");
    };

    const shouldShowFeedback = showFeedbackActions && configCollectFeedback;

    if (!showWorkflowButton && !shouldShowFeedback) {
        return null;
    }

    return (
        <>
            <div className="mt-3 space-y-2">
                <div className="flex items-center justify-start">
                    {showWorkflowButton && <ViewWorkflowButton onClick={handleViewWorkflowClick} />}
                    {shouldShowFeedback && (
                        <div className="flex items-center">
                            <Button tooltip="Like" variant="ghost" size="sm" className={`${submittedFeedbackType ? "!opacity-100" : ""}`} onClick={() => handleThumbClick("up")} disabled={!!submittedFeedbackType}>
                                <ThumbsUp className={`h-4 w-4 ${submittedFeedbackType === "up" ? "fill-[var(--color-brand-wMain)] text-[var(--color-brand-wMain)] !opacity-100" : ""}`} />
                            </Button>
                            <Button tooltip="Dislike" variant="ghost" size="sm" className={`${submittedFeedbackType ? "!opacity-100" : ""}`} onClick={() => handleThumbClick("down")} disabled={!!submittedFeedbackType}>
                                <ThumbsDown className={`h-4 w-4 ${submittedFeedbackType === "down" ? "fill-[var(--color-brand-wMain)] text-[var(--color-brand-wMain)] opacity-100" : ""}`} />
                            </Button>
                        </div>
                    )}
                    <MessageHoverButtons message={message} />
                </div>
            </div>
            {feedbackType && <FeedbackModal isOpen={isFeedbackModalOpen} onClose={handleModalClose} feedbackType={feedbackType} onSubmit={handleModalSubmit} />}
        </>
    );
};

const MessageContent = React.memo<{ message: MessageFE }>(({ message }) => {
    const [renderError, setRenderError] = useState<string | null>(null);
    const { sessionId } = useChatContext();

    // Extract text content from message parts
    const textContent =
        message.parts
            ?.filter(p => p.kind === "text")
            .map(p => (p as TextPart).text)
            .join("") || "";

    // Trim text for user messages to prevent trailing whitespace issues
    const displayText = message.isUser ? textContent.trim() : textContent;

    const renderContent = () => {
        if (message.isError) {
            return (
                <div className="flex items-center">
                    <AlertCircle className="mr-2 self-start text-[var(--color-error-wMain)]" />
                    <MarkdownHTMLConverter>{displayText}</MarkdownHTMLConverter>
                </div>
            );
        }

        const embeddedContent = extractEmbeddedContent(displayText);
        if (embeddedContent.length === 0) {
            return <MarkdownHTMLConverter>{displayText}</MarkdownHTMLConverter>;
        }

        let modifiedText = displayText;
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
                        <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment, sessionId)} isEmbedded={true} />
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

    // Wrap AI messages with SelectableMessageContent for text selection
    if (!message.isUser) {
        return (
            <SelectableMessageContent messageId={message.metadata?.messageId || ""} isAIMessage={true}>
                {renderContent()}
            </SelectableMessageContent>
        );
    }

    return renderContent();
});

const MessageWrapper = React.memo<{ message: MessageFE; children: ReactNode; className?: string }>(({ message, children, className }) => {
    return <div className={`mt-1 space-y-1 ${message.isUser ? "ml-auto" : "mr-auto"} ${className}`}>{children}</div>;
});

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
    const { openSidePanelTab, setTaskIdInSidePanel } = chatContext;

    if (message.isStatusBubble) {
        return null;
    }

    if (message.authenticationLink) {
        return <AuthenticationMessage message={message} />;
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

    const hasContent = groupedParts.some(p => (p.kind === "text" && p.text.trim()) || p.kind === "file" || p.kind === "artifact");
    if (!hasContent) {
        return null;
    }

    const variant = message.isUser ? "sent" : "received";
    const showWorkflowButton = !message.isUser && message.isComplete && !!message.taskId && !!isLastWithTaskId;
    const showFeedbackActions = !message.isUser && message.isComplete && !!message.taskId && !!isLastWithTaskId;

    const handleViewWorkflowClick = () => {
        if (message.taskId) {
            setTaskIdInSidePanel(message.taskId);
            openSidePanelTab("workflow");
        }
    };

    // Helper function to render artifact/file parts
    const renderArtifactOrFilePart = (part: ArtifactPart | FilePart, index: number) => {
        // Create unique key for expansion state using taskId (or messageId) + filename
        const uniqueKey = message.taskId
            ? `${message.taskId}-${part.kind === "file" ? (part as FilePart).file.name : (part as ArtifactPart).name}`
            : message.metadata?.messageId
              ? `${message.metadata.messageId}-${part.kind === "file" ? (part as FilePart).file.name : (part as ArtifactPart).name}`
              : undefined;

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
            return <ArtifactMessage key={`part-file-${index}`} status="completed" name={attachment.name} fileAttachment={attachment} uniqueKey={uniqueKey} />;
        }
        if (part.kind === "artifact") {
            const artifactPart = part as ArtifactPart;
            switch (artifactPart.status) {
                case "completed":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="completed" name={artifactPart.name} fileAttachment={artifactPart.file!} uniqueKey={uniqueKey} />;
                case "in-progress":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="in-progress" name={artifactPart.name} bytesTransferred={artifactPart.bytesTransferred!} uniqueKey={uniqueKey} />;
                case "failed":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="failed" name={artifactPart.name} error={artifactPart.error} uniqueKey={uniqueKey} />;
                default:
                    return null;
            }
        }
        return null;
    };

    // Find the index of the last part with content
    const lastPartIndex = groupedParts.length - 1;
    const lastPartKind = groupedParts[lastPartIndex]?.kind;

    return (
        <div key={message.metadata?.messageId} className="space-y-6">
            {/* Render parts in their original order to preserve interleaving */}
            {groupedParts.map((part, index) => {
                const isLastPart = index === lastPartIndex;

                if (part.kind === "text") {
                    // Skip rendering empty or whitespace-only text parts
                    const textContent = (part as TextPart).text;
                    if (!textContent || !textContent.trim()) {
                        // If this is the last part and it's empty, still render actions if needed
                        if (isLastPart && (showWorkflowButton || showFeedbackActions)) {
                            return (
                                <div key={`part-${index}`} className={`flex ${message.isUser ? "justify-end pr-4" : "justify-start pl-4"}`}>
                                    <MessageActions message={message} showWorkflowButton={!!showWorkflowButton} showFeedbackActions={!!showFeedbackActions} handleViewWorkflowClick={handleViewWorkflowClick} />
                                </div>
                            );
                        }
                        return null;
                    }

                    return (
                        <ChatBubble key={`part-${index}`} variant={variant}>
                            <ChatBubbleMessage variant={variant}>
                                <MessageContent message={{ ...message, parts: [{ kind: "text", text: textContent }] }} />
                                {/* Show actions on the last part if it's text */}
                                {isLastPart && <MessageActions message={message} showWorkflowButton={!!showWorkflowButton} showFeedbackActions={!!showFeedbackActions} handleViewWorkflowClick={handleViewWorkflowClick} />}
                            </ChatBubbleMessage>
                        </ChatBubble>
                    );
                } else if (part.kind === "artifact" || part.kind === "file") {
                    return renderArtifactOrFilePart(part, index);
                }
                return null;
            })}

            {/* Show actions after artifacts if the last part is an artifact */}
            {lastPartKind === "artifact" || lastPartKind === "file" ? (
                <div className={`flex ${message.isUser ? "justify-end pr-4" : "justify-start pl-4"}`}>
                    <MessageActions message={message} showWorkflowButton={!!showWorkflowButton} showFeedbackActions={!!showFeedbackActions} handleViewWorkflowClick={handleViewWorkflowClick} />
                </div>
            ) : null}

            {/* Show hover buttons below bubble for user messages */}
            {message.isUser && (
                <div className="flex justify-end">
                    <MessageHoverButtons message={message} />
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
