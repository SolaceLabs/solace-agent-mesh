export { AudioRecorder } from "./AudioRecorder";
export { ChatInputArea } from "./ChatInputArea";
export { ChatMessage } from "./ChatMessage";
export { ChatSessionDeleteDialog } from "./ChatSessionDeleteDialog";
export { ChatSessionDialog } from "./ChatSessionDialog";
export { ChatSessions } from "./ChatSessions";
export { ChatSidePanel } from "./ChatSidePanel";
export { LoadingMessageRow } from "./LoadingMessageRow";
export { SessionSidePanel } from "./SessionSidePanel";
export { MoveSessionDialog } from "./MoveSessionDialog";
export { RecentChatsList } from "./RecentChatsList";
export { VariableDialog } from "./VariableDialog";
export { SessionSearch } from "./SessionSearch";
export { MessageHoverButtons } from "./MessageHoverButtons";
export { SessionActionMenu } from "./SessionActionMenu";
export { sessionCardStyles, sessionRowStyles, sessionTitleStyles } from "./sessionCardStyles";
export { ShareNotification } from "./ShareNotification";
export { UserPresenceAvatars } from "./UserPresenceAvatars";
export { ShareNotificationMessage } from "./ShareNotificationMessage";
export { MessageAttribution } from "./MessageAttribution";
export { CollaborativeUserMessage } from "./CollaborativeUserMessage";
export { InlineProgressUpdates } from "./InlineProgressUpdates";
export { ContextUsageIndicator } from "./ContextUsageIndicator";
export * from "./file";
export * from "./selection";

// Artifact bar (chat-style file row) — pure flat-props component, safe to use
// outside a chat session (no context dependency). Other artifact components
// in `./artifact/*` rely on `useChatContext` so are intentionally not re-exported.
export { ArtifactBar, type ArtifactBarProps } from "./artifact/ArtifactBar";

// Artifact details row (filename + last-modified subtitle + info/download/delete
// action buttons). Optional version-selector hides when no ChatProvider is
// available, so it works inside other contexts (e.g. eval experiment results).
export { ArtifactDetails } from "./artifact/ArtifactDetails";

// Universal content preview renderer + helpers — pure components, safe to
// reuse anywhere a caller can supply the blob/text content directly.
export { ContentRenderer } from "./preview/ContentRenderer";
export { getRenderType, canPreviewArtifact, decodeBase64Content, encodeBase64Content, getFileContent } from "./preview/previewUtils";
