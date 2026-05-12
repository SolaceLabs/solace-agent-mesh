import React, { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import type { ArtifactInfo } from "@/lib/types";
import { MarkdownWrapper, MessageBanner } from "@/lib/components";
import { ArtifactBar } from "@/lib/components/chat/artifact/ArtifactBar";
import { ArtifactPreviewBody } from "@/lib/components/scheduled-tasks/ExecutionArtifactsView";
import { useExecutionArtifacts } from "@/lib/api/scheduled-tasks";
import { executionSessionId } from "@/lib/api/scheduled-tasks/service";
import { downloadFile } from "@/lib/utils/download";

// Match the chat page's LIVE-streaming behaviour (processChatEvent.ts
// appends parts in emission order, so text/artifact parts render interleaved
// where the agent produced them). The reload path
// (`deserializeChatMessages`) hoists artifacts to the top, but that diverges
// from what the user actually saw during the run — so we emit segments in
// textual order here to match the live view rather than the reload view.
const ARTIFACT_MARKER_REGEX = /«(artifact_return|artifact):([^»]+)»/g;

/** Strip a trailing :<digits> version suffix so "report.pdf:3" matches "report.pdf". */
function stripVersionSuffix(name: string): string {
    if (!name.includes(":")) return name;
    const parts = name.split(":");
    const last = parts[parts.length - 1];
    return /^\d+$/.test(last) ? parts.slice(0, -1).join(":") : name;
}

interface Segment {
    kind: "text" | "artifact";
    value: string;
}

/**
 * Walk `text` left-to-right and emit alternating text/artifact segments in
 * the order the agent produced them. Matches the chat page's live-streaming
 * render (parts are appended in emission order by processChatEvent). Each
 * artifact name is only emitted once so duplicated markers (e.g. the agent
 * referenced the file inline AND `_save_chat_task` appended the same marker
 * at end-of-text) don't render the card twice.
 */
function splitAgentText(text: string): { segments: Segment[]; mentionedNames: Set<string> } {
    const segments: Segment[] = [];
    const mentioned = new Set<string>();
    if (!text) return { segments, mentionedNames: mentioned };

    let lastIndex = 0;
    let match: RegExpExecArray | null;
    const re = new RegExp(ARTIFACT_MARKER_REGEX.source, "g");
    while ((match = re.exec(text)) !== null) {
        if (match.index > lastIndex) {
            segments.push({ kind: "text", value: text.slice(lastIndex, match.index) });
        }
        const name = stripVersionSuffix(match[2]);
        if (!mentioned.has(name)) {
            mentioned.add(name);
            segments.push({ kind: "artifact", value: name });
        }
        lastIndex = re.lastIndex;
    }
    if (lastIndex < text.length) {
        segments.push({ kind: "text", value: text.slice(lastIndex) });
    }
    return { segments, mentionedNames: mentioned };
}

interface ExecutionOutputProps {
    executionId: string;
    text: string;
    /** When false, omit the inline "No output yet" placeholder (caller renders its own fallback). */
    showPlaceholder?: boolean;
    /** Optional className applied to text segments — lets callers shrink to "snippet" size. */
    textClassName?: string;
    /**
     * When true, strip every artifact card from the output entirely — both
     * markers the agent emitted inline AND orphan artifacts the agent never
     * mentioned. Use on surfaces that have a dedicated artifacts tab/section
     * so the same files don't render in two places at once.
     */
    hideArtifacts?: boolean;
}

/**
 * Render an execution's agent response with artifacts inlined at their
 * `«artifact_return»` positions. Falls through to a tail-appended list for any
 * artifacts the agent produced but didn't mention in the text — without this,
 * older executions whose agents emit no markers would show the bare text and
 * lose their artifact tail entirely.
 */
export const ExecutionOutput: React.FC<ExecutionOutputProps> = ({ executionId, text, showPlaceholder = true, textClassName, hideArtifacts = false }) => {
    const { data: artifacts, isLoading, error } = useExecutionArtifacts(executionId);
    const sessionId = executionSessionId(executionId);

    const { segments, mentionedNames } = useMemo(() => splitAgentText(text), [text]);

    const artifactsByName = useMemo(() => {
        const map = new Map<string, ArtifactInfo>();
        for (const a of artifacts ?? []) {
            // First-write-wins; older versions stay reachable through any
            // explicit marker referencing the same name.
            if (!map.has(a.filename)) map.set(a.filename, a);
        }
        return map;
    }, [artifacts]);

    const orphanArtifacts = useMemo(() => (hideArtifacts ? [] : (artifacts ?? []).filter(a => !mentionedNames.has(a.filename))), [hideArtifacts, artifacts, mentionedNames]);

    if (error && !hideArtifacts) {
        return <MessageBanner variant="error" message={error instanceof Error ? error.message : "Failed to load artifacts"} />;
    }

    if (!text && (!artifacts || artifacts.length === 0)) {
        return showPlaceholder ? <div className="text-(--secondary-text-wMain) italic">No output yet.</div> : null;
    }

    return (
        <div className="space-y-3 text-sm break-words">
            {segments.map((segment, idx) => {
                if (segment.kind === "text") {
                    const trimmed = segment.value.trim();
                    if (!trimmed) return null;
                    return <MarkdownWrapper key={`seg-${idx}`} content={segment.value} className={textClassName ?? "text-sm"} />;
                }
                // When hideArtifacts is set, drop inline artifact segments
                // entirely so a sibling Artifacts tab/section can own the
                // file listing without duplication.
                if (hideArtifacts) return null;
                const artifact = artifactsByName.get(segment.value);
                return <InlineArtifact key={`seg-${idx}`} name={segment.value} artifact={artifact} sessionId={sessionId} isLoading={isLoading && !artifact} />;
            })}
            {/* Tail-append any artifacts the agent produced but didn't reference
                in the text (older executions / agents that don't emit markers). */}
            {orphanArtifacts.length > 0 && (
                <div className="space-y-2">
                    {orphanArtifacts.map(artifact => (
                        <InlineArtifact key={artifact.uri ?? `${artifact.filename}@${artifact.version ?? "latest"}`} name={artifact.filename} artifact={artifact} sessionId={sessionId} isLoading={false} />
                    ))}
                </div>
            )}
        </div>
    );
};

interface InlineArtifactProps {
    name: string;
    artifact: ArtifactInfo | undefined;
    sessionId: string;
    isLoading: boolean;
}

const InlineArtifact: React.FC<InlineArtifactProps> = ({ name, artifact, sessionId, isLoading }) => {
    const [expanded, setExpanded] = useState(false);

    if (!artifact) {
        // Marker referenced an artifact name we can't resolve in the artifact
        // list. Show a placeholder bar (still preserving the agent's textual
        // position) rather than dropping the marker silently.
        return (
            <div className="overflow-hidden rounded-md border border-(--secondary-w40)">
                <ArtifactBar filename={name} status={isLoading ? "in-progress" : "completed"} context="chat" />
                {isLoading && (
                    <div className="flex items-center gap-2 border-t bg-(--background-w10) p-3 text-xs text-(--secondary-text-wMain)">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Loading…
                    </div>
                )}
            </div>
        );
    }

    const handleDownload = () => downloadFile({ name: artifact.filename, mime_type: artifact.mime_type, size: artifact.size, uri: artifact.uri }, sessionId);

    const expandedBody = expanded ? (
        <div className="border-t bg-(--background-w10) p-4">
            <ArtifactPreviewBody artifact={artifact} sessionId={sessionId} onDownload={handleDownload} />
        </div>
    ) : null;

    return (
        <div className="overflow-hidden rounded-md border border-(--secondary-w40)">
            <ArtifactBar
                filename={artifact.filename}
                mimeType={artifact.mime_type}
                size={artifact.size}
                status="completed"
                context="chat"
                expandable
                expanded={expanded}
                onToggleExpand={() => setExpanded(v => !v)}
                expandedContent={expandedBody}
                actions={{ onDownload: handleDownload }}
            />
        </div>
    );
};
