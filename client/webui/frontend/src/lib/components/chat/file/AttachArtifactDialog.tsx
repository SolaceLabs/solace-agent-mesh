import React, { useEffect, useMemo, useRef, useState } from "react";
import { Folder, MessageSquare, Search } from "lucide-react";

import { Button, Checkbox, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Spinner } from "@/lib/components/ui";
import { useAllArtifacts, type ArtifactWithSession } from "@/lib/api/artifacts";
import { useDebounce } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { formatBytes } from "@/lib/utils/format";

import { getFileTypeColor } from "./FileIcon";
import { getExtensionLabel } from "./attachmentUtils";

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

    // Reset state when dialog closes so it opens fresh next time.
    useEffect(() => {
        if (!isOpen) {
            setSelectedKeys(new Set());
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
                // Ensure the outgoing artifact carries a resolved `uri` so downstream
                // consumers (the chat submit pipeline) don't need to re-resolve it.
                .map(({ artifact, resolvedUri }) => ({ ...artifact, uri: resolvedUri ?? artifact.uri })),
        [visibleArtifacts, selectedKeys]
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
                                    // Prefer project name over session name; pick the matching icon.
                                    const scopeName = artifact.projectName || artifact.sessionName;
                                    const ScopeIcon = artifact.projectName ? Folder : MessageSquare;
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
                                            <span className={cn("flex-shrink-0 rounded px-2 py-0.5 text-[10px] font-bold text-(--darkSurface-text)", getFileTypeColor(artifact.mime_type, artifact.filename))}>
                                                {getExtensionLabel(artifact.filename)}
                                            </span>
                                            <div className="min-w-0 flex-1">
                                                <div className="truncate text-sm font-medium text-(--primary-text-wMain)" title={artifact.filename}>
                                                    {artifact.filename}
                                                </div>
                                                <div className="flex items-center gap-2 text-xs text-(--secondary-text-wMain)">
                                                    <span className="truncate">{artifact.mime_type}</span>
                                                    <span aria-hidden>·</span>
                                                    <span>{formatBytes(artifact.size)}</span>
                                                    {scopeName && (
                                                        <>
                                                            <span aria-hidden>·</span>
                                                            <span className="flex min-w-0 items-center gap-1">
                                                                <ScopeIcon className="size-3 flex-shrink-0" />
                                                                <span className="truncate" title={scopeName}>
                                                                    {scopeName}
                                                                </span>
                                                            </span>
                                                        </>
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
