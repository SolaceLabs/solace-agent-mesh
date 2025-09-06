import React, { useState } from "react";
import type { ReactNode } from "react";

import { AlertCircle } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MessageBanner } from "@/lib/components";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactPart, FileAttachment, FilePart, MessageFE, TextPart } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";

import { ArtifactMessage, FileMessage } from "./file";
import { ContentRenderer } from "./preview/ContentRenderer";
import { extractEmbeddedContent } from "./preview/contentUtils";
import { decodeBase64Content } from "./preview/previewUtils";
import { downloadFile } from "@/lib/utils/download";
import type { ExtractedContent } from "./preview/contentUtils";

const RENDER_TYPES_WITH_RAW_CONTENT = ["image", "audio"];

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
                    <div key={`embedded-${index}`} className="my-2 h-auto w-md max-w-md overflow-hidden">
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
                {groupedParts.map((part, index) => {
                    if (part.kind === "text") {
                        return <MessageContent key={`part-text-${index}`} message={message} textContent={part.text} />;
                    }
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
                            <div key={`part-file-${index}`} className="my-2">
                                <ArtifactMessage status="completed" name={attachment.name} fileAttachment={attachment} />
                            </div>
                        );
                    }
                    if (part.kind === "artifact") {
                        const artifactPart = part as ArtifactPart;
                        switch (artifactPart.status) {
                            case "completed":
                                return (
                                    <div key={`part-artifact-${index}`} className="my-2">
                                        <ArtifactMessage status="completed" name={artifactPart.name} fileAttachment={artifactPart.file!} />
                                    </div>
                                );
                            case "in-progress":
                                return (
                                    <div key={`part-artifact-${index}`} className="my-2">
                                        <ArtifactMessage status="in-progress" name={artifactPart.name} bytesTransferred={artifactPart.bytesTransferred!} />
                                    </div>
                                );
                            case "failed":
                                return (
                                    <div key={`part-artifact-${index}`} className="my-2">
                                        <ArtifactMessage status="failed" name={artifactPart.name} error={artifactPart.error} />
                                    </div>
                                );
                            default:
                                return null;
                        }
                    }
                    return null;
                })}
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
        </>
    );
};
