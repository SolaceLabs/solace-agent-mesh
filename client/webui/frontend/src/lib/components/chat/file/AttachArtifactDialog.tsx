import React, { useEffect, useMemo, useRef, useState } from "react";
import { MessageSquare, Search } from "lucide-react";

import { Button, Checkbox, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner } from "@/lib/components/ui";
import { useAllArtifacts, useArtifactVersions, isProjectArtifact, type ArtifactWithSession } from "@/lib/api/artifacts";
import { useDebounce } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";

import { getFileTypeColor } from "./FileIcon";
import { ProjectBadge } from "./ProjectBadge";
import { getExtensionLabel } from "./attachmentUtils";

/**
 * Inline per-row version picker. The default is the resolved-latest version
 * provided by the bulk-list endpoint (a concrete number, not a "Latest"
 * sentinel — that label would have falsely implied live-sync semantics; in
 * practice the selected version is snapshot into the agent's namespace at
 * attach time and frozen). The full version list is lazy-loaded on first
 * open so a dialog with 30+ artifacts doesn't fan out N list_versions calls
 * upfront. Mirrors the look of the side-panel `ArtifactDetails` selector.
 */
const ArtifactVersionPicker: React.FC<{
    artifact: ArtifactWithSession;
    value: number;
    onValueChange: (value: number) => void;
}> = ({ artifact, value, onValueChange }) => {
    const [hasOpened, setHasOpened] = useState(false);
    const { data: lazyVersions, isLoading } = useArtifactVersions({
        sessionId: artifact.sessionId,
        projectId: artifact.projectId,
        filename: artifact.filename,
        enabled: hasOpened,
    });

    // Until the user opens the picker we only know the latest version (from
    // the bulk-list response). Render that single option; the lazy fetch
    // expands the list once they look.
    const versions = lazyVersions ?? (typeof artifact.version === "number" ? [artifact.version] : []);

    return (
        <Select
            value={value.toString()}
            onValueChange={v => onValueChange(parseInt(v, 10))}
            onOpenChange={open => {
                if (open) setHasOpened(true);
            }}
        >
            <SelectTrigger
                className="h-[16px] w-auto gap-1 py-0 text-xs shadow-none"
                onClick={e => {
                    // The row itself has an onClick that toggles selection — the
                    // version picker should be independent of that.
                    e.stopPropagation();
                }}
            >
                <SelectValue />
            </SelectTrigger>
            <SelectContent
                onClick={e => {
                    e.stopPropagation();
                }}
            >
                {isLoading && (
                    <div className="flex items-center justify-center py-1">
                        <Spinner size="small" variant="muted" />
                    </div>
                )}
                {versions.map(v => (
                    <SelectItem key={v} value={v.toString()}>
                        Version {v}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
};

// The agent-side translator requires the canonical 4-segment form
// `artifact://{app_name}/{user_id}/{session_id}/{filename}?version=N`. The
// 2-segment legacy form used elsewhere for display purposes is rejected
// when sent through `FilePart{uri}`. The bulk `/artifacts/all` endpoint
// returns the canonical URI on every record — if `uri` is missing here it
// means the backend couldn't resolve a version and the artifact isn't
// attachable, so we hide it rather than fabricate a broken URI.
const resolveArtifactUri = (artifact: ArtifactWithSession): string | null => {
    return artifact.uri ? artifact.uri : null;
};

/**
 * Apply a concrete version to a canonical artifact URI as `?version=N`,
 * replacing any pre-existing query. The version is always explicit (the
 * dialog resolved "latest" to a concrete number when the row was rendered)
 * so the snapshot semantics are visible end-to-end.
 */
const applyVersionToUri = (uri: string, version: number): string => {
    try {
        const url = new URL(uri);
        url.search = "";
        url.searchParams.set("version", version.toString());
        return url.toString();
    } catch {
        return uri;
    }
};

interface AttachArtifactDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onAttach: (artifacts: ArtifactWithSession[]) => void;
    /** Artifact URIs already attached to the current input — filtered out of results. */
    alreadyAttachedUris?: string[];
}

const keyFor = (a: ArtifactWithSession) => `${a.sessionId}::${a.filename}`;

export const AttachArtifactDialog: React.FC<AttachArtifactDialogProps> = ({ isOpen, onClose, onAttach, alreadyAttachedUris = [] }) => {
    const [searchQuery, setSearchQuery] = useState("");
    const debouncedSearch = useDebounce(searchQuery.trim(), 400);

    const { data: artifacts = [], isLoading, hasMore, loadMore, isLoadingMore } = useAllArtifacts(debouncedSearch || undefined);

    const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
    // Per-row version override; absent entry = the artifact's own
    // backend-resolved latest version. Keyed the same way as `selectedKeys` so
    // they can be looked up together when attaching.
    const [versionByKey, setVersionByKey] = useState<Map<string, number>>(new Map());

    // Reset state when dialog closes so it opens fresh next time.
    useEffect(() => {
        if (!isOpen) {
            setSelectedKeys(new Set());
            setVersionByKey(new Map());
            setSearchQuery("");
        }
    }, [isOpen]);

    const attachedUriSet = useMemo(() => new Set(alreadyAttachedUris.filter(Boolean)), [alreadyAttachedUris]);

    // An artifact must resolve to a URI to be attached by reference; also hide
    // ones already pinned to this message so the user can't attach duplicates.
    const visibleArtifacts = useMemo(() => artifacts.map(a => ({ artifact: a, resolvedUri: resolveArtifactUri(a) })).filter(({ resolvedUri }) => resolvedUri && !attachedUriSet.has(resolvedUri)), [artifacts, attachedUriSet]);

    // Infinite scroll sentinel, mirrors the pattern used on ArtifactsPage.
    const sentinelRef = useRef<HTMLLIElement>(null);
    useEffect(() => {
        const sentinel = sentinelRef.current;
        if (!sentinel || !hasMore || isLoadingMore) return;
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) loadMore();
            },
            { rootMargin: "100px" }
        );
        observer.observe(sentinel);
        return () => observer.disconnect();
    }, [hasMore, isLoadingMore, loadMore]);

    const toggleSelect = (artifact: ArtifactWithSession) => {
        const k = keyFor(artifact);
        setSelectedKeys(prev => {
            const next = new Set(prev);
            if (next.has(k)) next.delete(k);
            else next.add(k);
            return next;
        });
    };

    // Derive from `visibleArtifacts` so the count tracks what `handleAttach`
    // would actually attach: if a selected item is filtered out by the search,
    // it stops counting and the button label/disabled state stay in sync.
    const selectedArtifacts = useMemo(
        () =>
            visibleArtifacts
                .filter(({ artifact }) => selectedKeys.has(keyFor(artifact)))
                .map(({ artifact, resolvedUri }) => {
                    const baseUri = resolvedUri ?? artifact.uri;
                    // Use the per-row override if set, else the artifact's
                    // backend-resolved latest version. Either way, the URI
                    // always carries an explicit `?version=N` — no implicit
                    // "latest" semantics survive into the submit pipeline.
                    const versionChoice = versionByKey.get(keyFor(artifact)) ?? artifact.version;
                    const finalUri = baseUri && typeof versionChoice === "number" ? applyVersionToUri(baseUri, versionChoice) : baseUri;
                    return { ...artifact, uri: finalUri };
                }),
        [visibleArtifacts, selectedKeys, versionByKey]
    );

    const handleAttach = () => {
        if (selectedArtifacts.length === 0) return;
        onAttach(selectedArtifacts);
        onClose();
    };

    const selectedCount = selectedArtifacts.length;

    return (
        <Dialog
            open={isOpen}
            onOpenChange={open => {
                if (!open) onClose();
            }}
        >
            <DialogContent showCloseButton className="flex max-h-[70vh] flex-col rounded-lg sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Attach existing artifact</DialogTitle>
                </DialogHeader>

                <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
                    <div className="relative w-full">
                        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--secondary-text-wMain)" />
                        <Input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search artifacts by name, type, session, or project…" className="w-full pl-9" data-testid="attach-artifact-search" />
                    </div>

                    <div className="min-h-0 flex-1 overflow-y-auto rounded-md border bg-(--background-w10)">
                        {isLoading ? (
                            <div className="flex h-32 items-center justify-center">
                                <Spinner />
                            </div>
                        ) : visibleArtifacts.length === 0 ? (
                            <div className="flex h-32 items-center justify-center px-4 text-center text-sm text-(--secondary-text-wMain)">{searchQuery ? "No artifacts match your search." : "No artifacts available to attach."}</div>
                        ) : (
                            <ul role="listbox" aria-multiselectable="true" className="divide-y">
                                {visibleArtifacts.map(({ artifact }) => {
                                    const k = keyFor(artifact);
                                    const isSelected = selectedKeys.has(k);
                                    return (
                                        <li
                                            key={k}
                                            role="option"
                                            aria-selected={isSelected}
                                            onClick={() => toggleSelect(artifact)}
                                            onKeyDown={event => {
                                                if (event.key === "Enter" || event.key === " ") {
                                                    event.preventDefault();
                                                    toggleSelect(artifact);
                                                }
                                            }}
                                            tabIndex={0}
                                            className={cn("flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors hover:bg-(--primary-w10) focus:bg-(--primary-w10) focus:outline-none", isSelected && "bg-(--primary-w10)")}
                                        >
                                            <Checkbox checked={isSelected} />
                                            {/* Fixed-width pill so filenames line up vertically across rows
                                                regardless of the extension label (WEBP vs TXT vs DOCX vs WASM). */}
                                            <span className={cn("w-12 flex-shrink-0 rounded px-2 py-0.5 text-center text-[10px] font-bold text-(--darkSurface-text)", getFileTypeColor(artifact.mime_type, artifact.filename))}>
                                                {getExtensionLabel(artifact.filename)}
                                            </span>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2">
                                                    <div className="min-w-0 flex-1 truncate text-sm font-medium text-(--primary-text-wMain)" title={artifact.filename}>
                                                        {artifact.filename}
                                                    </div>
                                                    {/* Hide the picker for:
                                                        - project-scoped artifacts: project knowledge files only
                                                          expose their single latest version regardless of how many
                                                          versions exist within the project.
                                                        - single-version artifacts: nothing to pick.
                                                          Versions are 0-indexed and sequential, so a latest of 0
                                                          implies exactly one version. */}
                                                    {!isProjectArtifact(artifact) && typeof artifact.version === "number" && artifact.version > 0 && (
                                                        <ArtifactVersionPicker
                                                            artifact={artifact}
                                                            value={versionByKey.get(k) ?? artifact.version}
                                                            onValueChange={v => {
                                                                setVersionByKey(prev => {
                                                                    const next = new Map(prev);
                                                                    next.set(k, v);
                                                                    return next;
                                                                });
                                                            }}
                                                        />
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2 overflow-hidden text-xs whitespace-nowrap text-(--secondary-text-wMain)">
                                                    <span className="min-w-0 truncate">{artifact.mime_type}</span>
                                                    <span aria-hidden>·</span>
                                                    <span className="flex-shrink-0">{formatBytes(artifact.size)}</span>
                                                    {/* Project artifacts render the standard ProjectBadge —
                                                        same component used in RecentChatsPage / ArtifactsPage /
                                                        ChatPage so the visual treatment stays consistent. Session
                                                        artifacts keep the chat-bubble icon + chat title. */}
                                                    {artifact.projectName ? (
                                                        <>
                                                            <span aria-hidden>·</span>
                                                            <ProjectBadge text={artifact.projectName} className="flex-shrink-0" />
                                                        </>
                                                    ) : (
                                                        artifact.sessionName && (
                                                            <>
                                                                <span aria-hidden>·</span>
                                                                <span className="flex min-w-0 items-center gap-1">
                                                                    <MessageSquare className="size-3 flex-shrink-0" />
                                                                    <span className="truncate" title={artifact.sessionName}>
                                                                        {artifact.sessionName}
                                                                    </span>
                                                                </span>
                                                            </>
                                                        )
                                                    )}
                                                </div>
                                            </div>
                                        </li>
                                    );
                                })}
                                {hasMore && (
                                    <li ref={sentinelRef} className="flex h-12 items-center justify-center">
                                        {isLoadingMore && <Spinner />}
                                    </li>
                                )}
                            </ul>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button onClick={handleAttach} disabled={selectedCount === 0}>
                        {selectedCount === 0 ? "Attach" : `Attach ${selectedCount}`}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
