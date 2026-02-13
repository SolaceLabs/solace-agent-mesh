import React, { useState, useMemo } from "react";
import type { ReactNode } from "react";

import { AlertCircle, Quote, ThumbsDown, ThumbsUp } from "lucide-react";

import { ChatBubble, ChatBubbleMessage, MarkdownHTMLConverter, MarkdownWrapper, MessageBanner } from "@/lib/components";
import { Button } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, ArtifactPart, DataPart, FileAttachment, FilePart, MessageFE, RAGSearchResult, TextPart } from "@/lib/types";
import type { ChatContextValue } from "@/lib/contexts";
import { InlineResearchProgress, type ResearchProgressData } from "@/lib/components/research/InlineResearchProgress";
import { DeepResearchReportContent } from "@/lib/components/research/DeepResearchReportContent";
import { Sources } from "@/lib/components/web/Sources";
import { ImageSearchGrid } from "@/lib/components/research";
import { isDeepResearchReportFilename } from "@/lib/utils/deepResearchUtils";
import { TextWithCitations } from "./Citation";
import { parseCitations } from "@/lib/utils/citations";

import DOMPurify from "dompurify";
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
    sourcesElement?: React.ReactNode;
    /** Optional text content override */
    textContentOverride?: string;
}> = ({ message, showWorkflowButton, showFeedbackActions, handleViewWorkflowClick, sourcesElement, textContentOverride }) => {
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

    if (!showWorkflowButton && !shouldShowFeedback && !sourcesElement) {
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
                    <MessageHoverButtons message={message} textContentOverride={textContentOverride} />
                    {sourcesElement && <div className="ml-2">{sourcesElement}</div>}
                </div>
            </div>
            {feedbackType && <FeedbackModal isOpen={isFeedbackModalOpen} onClose={handleModalClose} feedbackType={feedbackType} onSubmit={handleModalSubmit} />}
        </>
    );
};

/**
 * Transform technical workflow error messages into user-friendly ones
 */
const getUserFriendlyErrorMessage = (technicalMessage: string): string => {
    // Pattern: "Workflow failed: Node 'X' failed: Node execution error: No FilePart found in message for structured schema"
    if (technicalMessage.includes("No FilePart found in message for structured schema")) {
        return "This workflow requires a file to be uploaded. Please attach a file and try again.";
    }

    // Pattern: "Workflow failed: Node 'X' failed: Node execution error: ..."
    if (technicalMessage.includes("Workflow failed:") && technicalMessage.includes("Node execution error:")) {
        const match = technicalMessage.match(/Node execution error:\s*(.+)$/);
        if (match) {
            return `The workflow encountered an error: ${match[1]}`;
        }
    }

    // Pattern: "Workflow failed: ..."
    if (technicalMessage.startsWith("Workflow failed:")) {
        return technicalMessage.replace(/^Workflow failed:\s*/, "The workflow encountered an error: ");
    }

    // Pattern: Generic task failure
    if (technicalMessage.toLowerCase().includes("task failed")) {
        return "The request could not be completed. Please try again or contact support.";
    }

    // Default: return the original message if no pattern matches
    return technicalMessage;
};

const MessageContent = React.memo<{ message: MessageFE; isStreaming?: boolean; highlightedText?: string | null }>(({ message, isStreaming, highlightedText }) => {
    const [renderError, setRenderError] = useState<string | null>(null);
    const { sessionId, ragData, openSidePanelTab, setTaskIdInSidePanel } = useChatContext();
    const contentRef = React.useRef<HTMLDivElement>(null);

    // Effect to highlight specific text when highlightedText changes
    React.useEffect(() => {
        if (!highlightedText || !contentRef.current) return;

        const highlightStyle = "background-color: color-mix(in srgb, var(--color-brand-wMain) 30%, transparent); color: inherit; transition: background-color 0.5s ease-out;";
        const highlightMarks: HTMLElement[] = [];

        // Normalize text for matching (collapse whitespace, handle line breaks)
        const normalizeText = (text: string) => text.replace(/\s+/g, " ").trim();
        const searchTextNormalized = normalizeText(highlightedText);

        // Helper: Collect all text nodes and build a position map
        const collectTextNodes = (container: HTMLElement): { node: Text; start: number; end: number }[] => {
            const textNodes: { node: Text; start: number; end: number }[] = [];
            const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
            let node: Text | null;
            let position = 0;

            while ((node = walker.nextNode() as Text | null)) {
                const text = node.textContent || "";
                if (text.length > 0) {
                    textNodes.push({
                        node,
                        start: position,
                        end: position + text.length,
                    });
                    position += text.length;
                }
            }
            return textNodes;
        };

        // Helper: Find text position within text nodes using simple string search
        const findTextInNodes = (textNodes: { node: Text; start: number; end: number }[], searchText: string): { found: boolean; nodeRanges: { node: Text; startOffset: number; endOffset: number }[] } => {
            // Concatenate all text from text nodes
            const fullText = textNodes.map(t => t.node.textContent || "").join("");

            // Normalize both texts for comparison
            const normalizedFullText = normalizeText(fullText);
            const normalizedSearchText = normalizeText(searchText);

            // Find the normalized search text in the normalized full text
            const normalizedIndex = normalizedFullText.indexOf(normalizedSearchText);

            if (normalizedIndex === -1) {
                // Try case-insensitive search
                const lowerNormalizedIndex = normalizedFullText.toLowerCase().indexOf(normalizedSearchText.toLowerCase());
                if (lowerNormalizedIndex === -1) {
                    return { found: false, nodeRanges: [] };
                }
            }

            // Build mapping from normalized positions back to original positions
            // This handles collapsed whitespace
            const normalizedToOriginal: number[] = [];
            let lastWasSpace = false;

            for (let i = 0; i < fullText.length; i++) {
                const char = fullText[i];
                const isSpace = /\s/.test(char);

                if (isSpace) {
                    if (!lastWasSpace) {
                        // This is the first space in a sequence - maps to a single space in normalized
                        normalizedToOriginal.push(i);
                    }
                    // Subsequent spaces don't add to normalizedToOriginal
                    lastWasSpace = true;
                } else {
                    normalizedToOriginal.push(i);
                    lastWasSpace = false;
                }
            }

            // Skip leading whitespace in mapping (since normalizeText trims)
            let leadingSpaceCount = 0;
            for (const char of fullText) {
                if (/\s/.test(char)) leadingSpaceCount++;
                else break;
            }

            // Adjust mapping for leading whitespace
            const trimmedMapping = normalizedToOriginal.filter(pos => pos >= leadingSpaceCount);

            // Find the actual index (using case-insensitive if needed)
            let actualNormalizedIndex = normalizedFullText.indexOf(normalizedSearchText);
            if (actualNormalizedIndex === -1) {
                actualNormalizedIndex = normalizedFullText.toLowerCase().indexOf(normalizedSearchText.toLowerCase());
            }

            if (actualNormalizedIndex === -1 || actualNormalizedIndex >= trimmedMapping.length) {
                return { found: false, nodeRanges: [] };
            }

            // Map normalized positions to original positions
            const searchEndIndex = Math.min(actualNormalizedIndex + normalizedSearchText.length - 1, trimmedMapping.length - 1);

            if (searchEndIndex < 0 || actualNormalizedIndex < 0) {
                return { found: false, nodeRanges: [] };
            }

            const originalStart = trimmedMapping[actualNormalizedIndex];
            const originalEnd = trimmedMapping[searchEndIndex] + 1;

            // Find which text nodes contain this range
            const nodeRanges: { node: Text; startOffset: number; endOffset: number }[] = [];
            let currentPos = 0;

            for (const { node } of textNodes) {
                const text = node.textContent || "";
                const nodeStart = currentPos;
                const nodeEnd = currentPos + text.length;

                if (nodeEnd > originalStart && nodeStart < originalEnd) {
                    // This node overlaps with our search range
                    const startOffset = Math.max(0, originalStart - nodeStart);
                    const endOffset = Math.min(text.length, originalEnd - nodeStart);

                    if (startOffset < endOffset) {
                        nodeRanges.push({ node, startOffset, endOffset });
                    }
                }

                currentPos = nodeEnd;
            }

            return { found: nodeRanges.length > 0, nodeRanges };
        };

        // Helper: Highlight portions of text nodes
        const highlightNodeRanges = (nodeRanges: { node: Text; startOffset: number; endOffset: number }[]): HTMLElement[] => {
            const marks: HTMLElement[] = [];

            for (const { node, startOffset, endOffset } of nodeRanges) {
                const text = node.textContent || "";
                const parent = node.parentNode;
                if (!parent) continue;

                // Get the text to be highlighted
                const highlightText = text.slice(startOffset, endOffset);

                // Skip whitespace-only nodes to prevent visual glitches
                if (/^\s*$/.test(highlightText)) {
                    continue;
                }

                // Create document fragment with before, highlighted, and after parts
                const frag = document.createDocumentFragment();

                if (startOffset > 0) {
                    frag.appendChild(document.createTextNode(text.slice(0, startOffset)));
                }

                const mark = document.createElement("mark");
                mark.style.cssText = highlightStyle;
                mark.textContent = highlightText;
                frag.appendChild(mark);
                marks.push(mark);

                if (endOffset < text.length) {
                    frag.appendChild(document.createTextNode(text.slice(endOffset)));
                }

                parent.replaceChild(frag, node);
            }

            return marks;
        };

        // Main logic: Try to find and highlight the text
        const textNodes = collectTextNodes(contentRef.current);

        // Strategy 1: Try exact match (handles multi-node spanning)
        let result = findTextInNodes(textNodes, highlightedText);

        // Strategy 2: If not found, try progressively shorter versions
        if (!result.found) {
            const words = searchTextNormalized.split(/\s+/);
            for (const wordCount of [Math.min(5, words.length), 4, 3, 2, 1]) {
                if (result.found) break;
                if (words.length < wordCount) continue;

                const searchText = words.slice(0, wordCount).join(" ");
                if (searchText.length < 3) continue;

                // Re-collect text nodes (in case DOM was modified)
                const freshTextNodes = collectTextNodes(contentRef.current!);
                result = findTextInNodes(freshTextNodes, searchText);
            }
        }

        // Strategy 3: Fuzzy match - find text containing most of the words
        if (!result.found && searchTextNormalized.length > 0) {
            const words = searchTextNormalized.split(/\s+/).filter(w => w.length >= 2);
            if (words.length > 0) {
                const freshTextNodes = collectTextNodes(contentRef.current!);
                const fullText = freshTextNodes.map(t => t.node.textContent || "").join("");
                const normalizedFullText = normalizeText(fullText).toLowerCase();

                // Find the best matching region that contains the most consecutive words
                for (let startWord = 0; startWord < words.length && !result.found; startWord++) {
                    for (let endWord = words.length; endWord > startWord && !result.found; endWord--) {
                        const searchPhrase = words.slice(startWord, endWord).join(" ").toLowerCase();
                        if (normalizedFullText.includes(searchPhrase)) {
                            // Found a match! Now find it properly
                            const latestTextNodes = collectTextNodes(contentRef.current!);
                            result = findTextInNodes(latestTextNodes, words.slice(startWord, endWord).join(" "));
                            break;
                        }
                    }
                }
            }
        }

        // Apply highlights if we found matches
        if (result.found && result.nodeRanges.length > 0) {
            const marks = highlightNodeRanges(result.nodeRanges);
            highlightMarks.push(...marks);
        }

        // Scroll and fade handling
        if (highlightMarks.length > 0) {
            // Scroll the first highlight into view
            highlightMarks[0].scrollIntoView({ behavior: "smooth", block: "center" });

            // Fade out all highlights after 3 seconds
            setTimeout(() => {
                highlightMarks.forEach(mark => {
                    mark.style.backgroundColor = "transparent";
                });
            }, 3000);

            // Remove all mark elements after fade completes
            setTimeout(() => {
                highlightMarks.forEach(mark => {
                    if (mark.parentNode) {
                        const textNode = document.createTextNode(mark.textContent || "");
                        mark.parentNode.replaceChild(textNode, mark);
                    }
                });
            }, 3500);
        }
    }, [highlightedText]);

    // Extract text content from message parts
    let textContent =
        message.parts
            ?.filter(p => p.kind === "text")
            .map(p => (p as TextPart).text)
            .join("") || "";

    // For user messages with contextQuote, strip the "Context: ..." prefix from the displayed text
    // The context is shown separately above the message bubble via the contextQuote field
    if (message.isUser && message.contextQuote) {
        // Match and remove the context prefix pattern: Context: "quoted text"\n\n
        const contextPrefixRegex = /^Context:\s*"[^"]*"\s*\n\n/;
        textContent = textContent.replace(contextPrefixRegex, "");
    }

    // Trim text for user messages to prevent trailing whitespace issues
    const displayText = message.isUser ? textContent.trim() : textContent;

    // Parse citations from text and match to RAG sources
    // Aggregate sources from ALL RAG entries for this task, not just the last one.
    // When there are multiple web searches (multiple tool calls), each creates a separate RAG entry.
    const taskRagData = useMemo(() => {
        if (!message.taskId || !ragData) return undefined;
        const matches = ragData.filter(r => r.taskId === message.taskId);
        if (matches.length === 0) return undefined;

        // If only one entry, return it directly
        if (matches.length === 1) return matches[0];

        // Aggregate all sources from all matching RAG entries
        // Use the last entry as the base (for query, title, etc.) but combine all sources
        const lastEntry = matches[matches.length - 1];
        const allSources = matches.flatMap(r => r.sources || []);

        // Deduplicate sources by citationId (keep the first occurrence)
        const seenCitationIds = new Set<string>();
        const uniqueSources = allSources.filter(source => {
            const citationId = source.citationId;
            if (!citationId || seenCitationIds.has(citationId)) {
                return false;
            }
            seenCitationIds.add(citationId);
            return true;
        });

        return {
            ...lastEntry,
            sources: uniqueSources,
        };
    }, [message.taskId, ragData]);

    const citations = useMemo(() => {
        if (message.isUser) return [];
        return parseCitations(displayText, taskRagData);
    }, [displayText, taskRagData, message.isUser]);

    // Extract embedded content and compute modified text at component level
    const embeddedContent = useMemo(() => extractEmbeddedContent(displayText), [displayText]);

    const { modifiedText, contentElements } = useMemo(() => {
        if (embeddedContent.length === 0) {
            return { modifiedText: displayText, contentElements: [] };
        }

        let modText = displayText;
        const elements: ReactNode[] = [];
        embeddedContent.forEach((item: ExtractedContent, index: number) => {
            modText = modText.replace(item.originalMatch, "");

            if (item.type === "file") {
                const fileAttachment: FileAttachment = {
                    name: item.filename || "downloaded_file",
                    content: item.content,
                    mime_type: item.mimeType,
                };
                elements.push(
                    <div key={`embedded-file-${index}`} className="my-2">
                        <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment, sessionId)} isEmbedded={true} />
                    </div>
                );
            } else if (!RENDER_TYPES_WITH_RAW_CONTENT.includes(item.type)) {
                const finalContent = decodeBase64Content(item.content);
                if (finalContent) {
                    elements.push(
                        <div key={`embedded-${index}`} className="my-2 h-auto w-md max-w-md">
                            <ContentRenderer content={finalContent} rendererType={item.type} mime_type={item.mimeType} setRenderError={setRenderError} ragData={taskRagData} />
                        </div>
                    );
                }
            }
        });

        return { modifiedText: modText, contentElements: elements };
    }, [embeddedContent, displayText, sessionId, setRenderError, taskRagData]);

    // Parse citations from modified text
    const modifiedCitations = useMemo(() => {
        if (message.isUser) return [];
        return parseCitations(modifiedText, taskRagData);
    }, [modifiedText, taskRagData, message.isUser]);

    const handleCitationClick = () => {
        // Open RAG panel when citation is clicked
        if (message.taskId) {
            setTaskIdInSidePanel(message.taskId);
            openSidePanelTab("rag");
        }
    };

    // If user message has displayHtml (with mention chips), render that instead
    if (message.isUser && message.displayHtml) {
        // Strip out any embedded context quote HTML from displayHtml
        // (for backward compatibility with old messages that had context embedded in displayHtml)
        // The context quote is now rendered separately above the message bubble

        const parser = new DOMParser();
        const doc = parser.parseFromString(message.displayHtml, "text/html");

        // Remove all context-quote-badge elements
        const quoteBadges = doc.querySelectorAll(".context-quote-badge");
        quoteBadges.forEach(badge => badge.remove());

        // Get the cleaned HTML from body
        const htmlToRender = doc.body.innerHTML;

        // Sanitize the HTML to prevent XSS
        // Allow mention chips and their data attributes
        const cleanHtml = DOMPurify.sanitize(htmlToRender, {
            ALLOWED_TAGS: ["span", "br", "div", "svg", "path"],
            ALLOWED_ATTR: ["class", "contenteditable", "data-internal", "data-person-id", "data-person-name", "data-display", "xmlns", "width", "height", "viewBox", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "d"],
        });

        return <div className="message-with-mentions break-words whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: cleanHtml }} />;
    }

    const renderContent = () => {
        if (message.isError) {
            const friendlyErrorMessage = getUserFriendlyErrorMessage(displayText);
            return (
                <div className="flex items-center">
                    <AlertCircle className="mr-2 self-start text-[var(--color-error-wMain)]" />
                    <MarkdownHTMLConverter>{friendlyErrorMessage}</MarkdownHTMLConverter>
                </div>
            );
        }

        if (embeddedContent.length === 0) {
            // Use MarkdownWrapper for streaming (smooth animation), TextWithCitations otherwise (citation support)
            if (isStreaming) {
                return <MarkdownWrapper content={displayText} isStreaming={isStreaming} />;
            }
            // Render text with citations if any exist
            if (citations.length > 0) {
                return <TextWithCitations text={displayText} citations={citations} onCitationClick={handleCitationClick} />;
            }
            return <MarkdownHTMLConverter>{displayText}</MarkdownHTMLConverter>;
        }

        return (
            <div>
                {renderError && <MessageBanner variant="error" message="Error rendering preview" />}
                {isStreaming ? (
                    <MarkdownWrapper content={modifiedText} isStreaming={isStreaming} />
                ) : modifiedCitations.length > 0 ? (
                    <TextWithCitations text={modifiedText} citations={modifiedCitations} onCitationClick={handleCitationClick} />
                ) : (
                    <MarkdownHTMLConverter>{modifiedText}</MarkdownHTMLConverter>
                )}
                {contentElements}
            </div>
        );
    };

    // Wrap AI messages with SelectableMessageContent for text selection
    if (!message.isUser) {
        return (
            <div ref={contentRef}>
                <SelectableMessageContent messageId={message.metadata?.messageId || ""} taskId={message.taskId} isAIMessage={true}>
                    {renderContent()}
                </SelectableMessageContent>
            </div>
        );
    }

    return <div ref={contentRef}>{renderContent()}</div>;
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

interface DeepResearchReportInfo {
    artifact: ArtifactInfo;
    sessionId: string;
    ragData?: RAGSearchResult;
}

// Component to render deep research report with TTS support
const DeepResearchReportBubble: React.FC<{
    deepResearchReportInfo: DeepResearchReportInfo;
    message: MessageFE;
    onContentLoaded?: (content: string) => void;
}> = ({ deepResearchReportInfo, message, onContentLoaded }) => {
    return (
        <ChatBubble variant="received">
            <ChatBubbleMessage variant="received">
                <SelectableMessageContent messageId={message.metadata?.messageId || ""} taskId={message.taskId} isAIMessage={true}>
                    <DeepResearchReportContent artifact={deepResearchReportInfo.artifact} sessionId={deepResearchReportInfo.sessionId} ragData={deepResearchReportInfo.ragData} onContentLoaded={onContentLoaded} />
                </SelectableMessageContent>
            </ChatBubbleMessage>
        </ChatBubble>
    );
};

const getChatBubble = (
    message: MessageFE,
    chatContext: ChatContextValue,
    isLastWithTaskId?: boolean,
    isStreaming?: boolean,
    sourcesElement?: React.ReactNode,
    deepResearchReportInfo?: DeepResearchReportInfo,
    onReportContentLoaded?: (content: string) => void,
    reportContentOverride?: string,
    highlightedText?: string | null
): React.ReactNode => {
    const { openSidePanelTab, setTaskIdInSidePanel, ragData } = chatContext;

    if (message.isStatusBubble) {
        return null;
    }

    if (message.authenticationLink) {
        return <AuthenticationMessage message={message} />;
    }

    // Check for deep research progress data
    const progressPart = message.parts?.find(p => p.kind === "data") as DataPart | undefined;
    const hasDeepResearchProgress = progressPart?.data && (progressPart.data as { type?: string }).type === "deep_research_progress";

    // Show progress block at the top if we have progress data and research is not complete
    if (hasDeepResearchProgress && !message.isComplete) {
        const data = progressPart!.data as unknown as ResearchProgressData;
        const taskRagData = ragData?.filter(r => r.taskId === message.taskId);
        const hasOtherContent = message.parts?.some(p => (p.kind === "text" && (p as TextPart).text.trim()) || p.kind === "artifact" || p.kind === "file");

        // Always show progress block for active research (before completion)
        const progressBlock = (
            <div className="my-2">
                <InlineResearchProgress progress={data} isComplete={false} ragData={taskRagData} />
            </div>
        );

        // If this is progress-only (no other content), just return the progress block
        if (!hasOtherContent) {
            return progressBlock;
        }

        // If there's other content, show progress block first, then the rest
        // Create a new message without the progress data part to avoid infinite recursion
        const messageWithoutProgress = {
            ...message,
            parts: message.parts?.filter(p => p.kind !== "data"),
        };

        return (
            <>
                {progressBlock}
                {getChatBubble(messageWithoutProgress, chatContext, isLastWithTaskId)}
            </>
        );
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

    // Debug logging for error messages
    if (message.isError) {
        console.log("[ChatMessage] Error message debug:", {
            isUser: message.isUser,
            isComplete: message.isComplete,
            taskId: message.taskId,
            isLastWithTaskId: isLastWithTaskId,
            showWorkflowButton,
            showFeedbackActions,
            parts: message.parts,
        });
    }

    const handleViewWorkflowClick = () => {
        if (message.taskId) {
            setTaskIdInSidePanel(message.taskId);
            openSidePanelTab("activity");
        }
    };

    // Helper function to render artifact/file parts
    const renderArtifactOrFilePart = (part: ArtifactPart | FilePart, index: number, isStreamingPart?: boolean) => {
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
            return <ArtifactMessage key={`part-file-${index}`} status="completed" name={attachment.name} fileAttachment={attachment} uniqueKey={uniqueKey} message={message} />;
        }
        if (part.kind === "artifact") {
            const artifactPart = part as ArtifactPart;
            switch (artifactPart.status) {
                case "completed":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="completed" name={artifactPart.name} fileAttachment={artifactPart.file!} uniqueKey={uniqueKey} message={message} />;
                case "in-progress":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="in-progress" name={artifactPart.name} bytesTransferred={artifactPart.bytesTransferred!} uniqueKey={uniqueKey} isStreaming={isStreamingPart} message={message} />;
                case "failed":
                    return <ArtifactMessage key={`part-artifact-${index}`} status="failed" name={artifactPart.name} error={artifactPart.error} uniqueKey={uniqueKey} message={message} />;
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
            {/* Render context quote above user message if present */}
            {message.isUser && message.contextQuote && (
                <div className="flex justify-end pr-4">
                    <button
                        className={`bg-muted/50 flex max-w-fit items-center gap-2 overflow-hidden rounded-md border px-3 py-2 text-sm ${message.contextQuoteSourceId ? "hover:bg-muted cursor-pointer transition-colors" : "cursor-default"}`}
                        onClick={() => {
                            if (message.contextQuoteSourceId) {
                                // Dispatch event to scroll to and highlight the quoted text in the source message
                                window.dispatchEvent(
                                    new CustomEvent("scroll-to-message", {
                                        detail: { taskId: message.contextQuoteSourceId, quotedText: message.contextQuote },
                                    })
                                );
                            }
                        }}
                        disabled={!message.contextQuoteSourceId}
                        title={message.contextQuoteSourceId ? "Click to scroll to original message" : undefined}
                    >
                        <Quote className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                        <span className="text-muted-foreground truncate italic">"{message.contextQuote}"</span>
                    </button>
                </div>
            )}
            {/* Render parts in their original order to preserve interleaving */}
            {groupedParts.map((part, index) => {
                const isLastPart = index === lastPartIndex;
                const shouldStream = isStreaming && isLastPart;

                if (part.kind === "text") {
                    // Skip rendering empty or whitespace-only text parts
                    const textContent = (part as TextPart).text;
                    if (!textContent || !textContent.trim()) {
                        // If this is the last part and it's empty, still render actions if needed
                        if (isLastPart && (showWorkflowButton || showFeedbackActions)) {
                            return (
                                <div key={`part-${index}`} className={`flex ${message.isUser ? "justify-end pr-4" : "justify-start pl-4"}`}>
                                    <MessageActions
                                        message={message}
                                        showWorkflowButton={!!showWorkflowButton}
                                        showFeedbackActions={!!showFeedbackActions}
                                        handleViewWorkflowClick={handleViewWorkflowClick}
                                        textContentOverride={reportContentOverride}
                                    />
                                </div>
                            );
                        }
                        return null;
                    }

                    return (
                        <ChatBubble key={`part-${index}`} variant={variant}>
                            <ChatBubbleMessage variant={variant}>
                                <MessageContent message={{ ...message, parts: [{ kind: "text", text: textContent }] }} isStreaming={shouldStream} highlightedText={highlightedText} />
                                {/* Show actions on the last part if it's text */}
                                {isLastPart && (
                                    <MessageActions
                                        message={message}
                                        showWorkflowButton={!!showWorkflowButton}
                                        showFeedbackActions={!!showFeedbackActions}
                                        handleViewWorkflowClick={handleViewWorkflowClick}
                                        sourcesElement={sourcesElement}
                                        textContentOverride={reportContentOverride}
                                    />
                                )}
                            </ChatBubbleMessage>
                        </ChatBubble>
                    );
                } else if (part.kind === "artifact" || part.kind === "file") {
                    return renderArtifactOrFilePart(part, index, shouldStream);
                }
                return null;
            })}

            {/* Show deep research report content inline (without References and Methodology sections) */}
            {deepResearchReportInfo && <DeepResearchReportBubble deepResearchReportInfo={deepResearchReportInfo} message={message} onContentLoaded={onReportContentLoaded} />}

            {/* Show actions after artifacts if the last part is an artifact */}
            {lastPartKind === "artifact" || lastPartKind === "file" ? (
                <div className={`flex ${message.isUser ? "justify-end pr-4" : "justify-start pl-4"}`}>
                    <MessageActions
                        message={message}
                        showWorkflowButton={!!showWorkflowButton}
                        showFeedbackActions={!!showFeedbackActions}
                        handleViewWorkflowClick={handleViewWorkflowClick}
                        sourcesElement={sourcesElement}
                        textContentOverride={reportContentOverride}
                    />
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
export const ChatMessage: React.FC<{ message: MessageFE; isLastWithTaskId?: boolean; isStreaming?: boolean }> = ({ message, isLastWithTaskId, isStreaming }) => {
    const chatContext = useChatContext();
    const { ragData, openSidePanelTab, setTaskIdInSidePanel, artifacts, sessionId } = chatContext;

    // State to track deep research report content for message actions functionality
    const [reportContent, setReportContent] = useState<string | null>(null);

    // State for highlight animation when scrolled to from context quote link
    const [isHighlighted, setIsHighlighted] = useState(false);
    const [highlightedText, setHighlightedText] = useState<string | null>(null);
    const messageRef = React.useRef<HTMLDivElement>(null);

    // Listen for scroll-to-message events
    React.useEffect(() => {
        const handleScrollToMessage = (event: Event) => {
            const customEvent = event as CustomEvent;
            const { taskId, quotedText } = customEvent.detail;

            // Check if this message matches the target taskId
            if (message.taskId === taskId && messageRef.current) {
                // Scroll the message into view
                messageRef.current.scrollIntoView({ behavior: "smooth", block: "center" });

                // If we have quoted text, highlight just that portion
                if (quotedText) {
                    setHighlightedText(quotedText);
                    setTimeout(() => setHighlightedText(null), 2000);
                } else {
                    // Fallback to highlighting the entire message
                    setIsHighlighted(true);
                    setTimeout(() => setIsHighlighted(false), 2000);
                }
            }
        };

        window.addEventListener("scroll-to-message", handleScrollToMessage);
        return () => {
            window.removeEventListener("scroll-to-message", handleScrollToMessage);
        };
    }, [message.taskId]);

    // Get RAG metadata for this task
    const taskRagData = useMemo(() => {
        if (!message?.taskId || !ragData) return undefined;
        return ragData.filter(r => r.taskId === message.taskId);
    }, [message?.taskId, ragData]);

    // Find deep research report artifact in the message
    const deepResearchReportArtifact = useMemo(() => {
        if (!message) return null;

        // Check if this is a completed deep research message
        const hasProgressPart = message.parts?.some(p => {
            if (p.kind === "data") {
                const data = (p as DataPart).data as unknown as ResearchProgressData;
                return data?.type === "deep_research_progress";
            }
            return false;
        });

        const hasRagSources = taskRagData && taskRagData.length > 0 && taskRagData.some(r => r.sources && r.sources.length > 0);
        const hasDeepResearchRagData = taskRagData?.some(r => r.searchType === "deep_research");
        const isDeepResearchComplete = message.isComplete && (hasProgressPart || hasDeepResearchRagData) && hasRagSources;

        if (!isDeepResearchComplete || !isLastWithTaskId) return null;

        // Look for artifact parts in the message that match deep research report pattern
        const artifactParts = message.parts?.filter(p => p.kind === "artifact") as ArtifactPart[] | undefined;

        // First priority: Find the report artifact from this message's artifact parts
        // This ensures we get the correct report for this specific task
        if (artifactParts && artifactParts.length > 0) {
            for (const part of artifactParts) {
                if (part.status === "completed" && isDeepResearchReportFilename(part.name)) {
                    const fullArtifact = artifacts.find(a => a.filename === part.name);
                    if (fullArtifact) {
                        return fullArtifact;
                    }
                }
            }
        }

        // Second priority: Use artifact filename from RAG metadata
        // The backend stores the artifact filename in the RAG metadata for this purpose
        if (taskRagData && taskRagData.length > 0) {
            // Get the last RAG data entry which should have the artifact filename
            const lastRagData = taskRagData[taskRagData.length - 1];
            const artifactFilenameFromRag = lastRagData.metadata?.artifactFilename as string | undefined;
            if (artifactFilenameFromRag) {
                const matchedArtifact = artifacts.find(a => a.filename === artifactFilenameFromRag);
                if (matchedArtifact) {
                    return matchedArtifact;
                }
            }
        }

        // Only use global artifacts list if there's exactly one report artifact
        // This handles edge cases but avoids showing the wrong report when there are multiple
        const allReportArtifacts = artifacts.filter(a => isDeepResearchReportFilename(a.filename));
        if (allReportArtifacts.length === 1) {
            return allReportArtifacts[0];
        }

        // If there are multiple report artifacts and we couldn't find one,
        // don't show any inline report to avoid showing the wrong one
        return null;
    }, [message, isLastWithTaskId, artifacts, taskRagData]);

    // Get the last RAG data entry for this task (for citations in report)
    const lastTaskRagData = useMemo(() => {
        if (!taskRagData || taskRagData.length === 0) return undefined;
        return taskRagData[taskRagData.length - 1];
    }, [taskRagData]);

    // Early return after all hooks
    if (!message) {
        return null;
    }

    // Check if this is a completed deep research message
    // Check both for progress data part (during session) and ragData search_type (after refresh)
    const hasProgressPart = message.parts?.some(p => {
        if (p.kind === "data") {
            const data = (p as DataPart).data as unknown as ResearchProgressData;
            return data?.type === "deep_research_progress";
        }
        return false;
    });

    const hasRagSources = taskRagData && taskRagData.length > 0 && taskRagData.some(r => r.sources && r.sources.length > 0);

    // Check if ragData indicates deep research
    const hasDeepResearchRagData = taskRagData?.some(r => r.searchType === "deep_research");

    const isDeepResearchComplete = message.isComplete && (hasProgressPart || hasDeepResearchRagData) && hasRagSources;

    // Check if this is a completed web search message (has web_search sources but not deep research)
    const isWebSearchComplete = message.isComplete && !isDeepResearchComplete && hasRagSources && taskRagData?.some(r => r.searchType === "web_search");

    // Check if this is a completed document search message (has document_search sources)
    const isDocumentSearchComplete = message.isComplete && !isDeepResearchComplete && hasRagSources && taskRagData?.some(r => r.searchType === "document_search");

    // Handler for sources click (works for deep research, web search, and document search)
    const handleSourcesClick = () => {
        if (message.taskId) {
            setTaskIdInSidePanel(message.taskId);
            openSidePanelTab("rag");
        }
    };

    return (
        <div ref={messageRef} data-task-id={message.taskId} className={`transition-all duration-500 ${isHighlighted ? "ring-primary/50 bg-primary/5 rounded-lg ring-2" : ""}`}>
            {/* Show progress block at the top for completed deep research - only for the last message with this taskId */}
            {isDeepResearchComplete &&
                hasRagSources &&
                isLastWithTaskId &&
                (() => {
                    // Filter to only show fetched sources (not snippets)
                    const allSources = taskRagData.flatMap(r => r.sources);
                    const fetchedSources = allSources.filter(source => {
                        const wasFetched = source.metadata?.fetched === true || source.metadata?.fetch_status === "success" || (source.contentPreview && source.contentPreview.includes("[Full Content Fetched]"));
                        return wasFetched;
                    });

                    return (
                        <div className="mb-4">
                            <InlineResearchProgress
                                progress={{
                                    type: "deep_research_progress",
                                    phase: "writing",
                                    status_text: "Research complete",
                                    progress_percentage: 100,
                                    current_iteration: 0,
                                    total_iterations: 0,
                                    sources_found: fetchedSources.length,
                                    current_query: "",
                                    fetching_urls: [],
                                    elapsed_seconds: 0,
                                    max_runtime_seconds: 0,
                                }}
                                isComplete={true}
                                ragData={taskRagData}
                            />
                        </div>
                    );
                })()}
            {getChatBubble(
                message,
                chatContext,
                isLastWithTaskId,
                isStreaming,
                // Show sources element for deep research, web search, and document search (in message actions area)
                !message.isUser && (isDeepResearchComplete || isWebSearchComplete || isDocumentSearchComplete) && hasRagSources
                    ? (() => {
                          const allSources = taskRagData.flatMap(r => r.sources);

                          // For deep research: filter to only show fetched sources (not snippets)
                          // For web search: show all sources including images (images with source links will be shown)
                          const sourcesToShow = isDeepResearchComplete
                              ? allSources.filter(source => {
                                    const sourceType = source.sourceType || "web";
                                    // For images in deep research: include if they have a source link
                                    if (sourceType === "image") {
                                        return source.sourceUrl || source.metadata?.link;
                                    }
                                    const wasFetched = source.metadata?.fetched === true || source.metadata?.fetch_status === "success" || (source.contentPreview && source.contentPreview.includes("[Full Content Fetched]"));
                                    return wasFetched;
                                })
                              : allSources.filter(source => {
                                    const sourceType = source.sourceType || "web";
                                    // For images in web search: include if they have a source link
                                    if (sourceType === "image") {
                                        return source.sourceUrl || source.metadata?.link;
                                    }
                                    return true;
                                });

                          // Only render if we have sources
                          if (sourcesToShow.length === 0) return null;

                          return <Sources ragMetadata={{ sources: sourcesToShow }} isDeepResearch={isDeepResearchComplete} onDeepResearchClick={handleSourcesClick} />;
                      })()
                    : undefined,
                // Pass deep research report info if available
                isDeepResearchComplete && isLastWithTaskId && deepResearchReportArtifact && sessionId ? { artifact: deepResearchReportArtifact, sessionId, ragData: lastTaskRagData } : undefined,
                // Callback to capture report content for TTS/copy
                setReportContent,
                // Pass report content to MessageActions for TTS/copy
                reportContent || undefined,
                // Pass highlighted text for scroll-to-source feature
                highlightedText
            )}

            {/* Render images separately at the end for web search */}
            {!message.isUser &&
                isWebSearchComplete &&
                hasRagSources &&
                (() => {
                    const allSources = taskRagData.flatMap(r => r.sources);
                    const imageResults = allSources
                        .filter(source => {
                            const sourceType = source.sourceType || "web";
                            return sourceType === "image" && source.metadata?.imageUrl;
                        })
                        .map(source => ({
                            imageUrl: source.metadata!.imageUrl,
                            title: source.metadata?.title || source.filename,
                            link: source.sourceUrl || source.metadata?.link || source.metadata!.imageUrl,
                        }));

                    if (imageResults.length > 0) {
                        return (
                            <div className="mt-4">
                                <ImageSearchGrid images={imageResults} />
                            </div>
                        );
                    }
                    return null;
                })()}

            {getUploadedFiles(message)}
        </div>
    );
};
