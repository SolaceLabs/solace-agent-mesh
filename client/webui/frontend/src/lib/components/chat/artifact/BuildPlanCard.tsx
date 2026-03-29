import React, { useEffect, useMemo, useRef, useState } from "react";

import { Bot, BookOpen, Globe, Plug, Workflow } from "lucide-react";
import yaml from "js-yaml";

import { Spinner } from "@/lib/components/ui/spinner";
import { useChatContext } from "@/lib/hooks";

/** Minimal subset of the build manifest we need for rendering. */
interface BuildManifestPartial {
    name?: string;
    display_name?: string;
    description?: string;
    components?: Array<{ type?: string }>;
}

const COMPONENT_TYPE_ORDER = ["gateway", "workflow", "agent", "skill", "connector"] as const;
const COMPONENT_ICON_MAP: Record<string, typeof Bot> = {
    workflow: Workflow,
    connector: Plug,
    gateway: Globe,
    skill: BookOpen,
    agent: Bot,
};

/**
 * Trims partial streaming YAML to the last complete line (ending with \n)
 * so that yaml.load() doesn't choke on a half-written value.
 * Once `isComplete` is true, the full content is used as-is.
 */
function trimToCompleteYaml(raw: string, isComplete: boolean): string {
    if (isComplete) return raw;
    const lastNewline = raw.lastIndexOf("\n");
    if (lastNewline <= 0) return "";
    return raw.slice(0, lastNewline + 1);
}

function parsePartialManifest(raw: string, isComplete: boolean): BuildManifestPartial | null {
    const trimmed = trimToCompleteYaml(raw, isComplete);
    if (!trimmed) return null;
    try {
        const doc = yaml.load(trimmed);
        if (!doc || typeof doc !== "object") return null;
        return doc as BuildManifestPartial;
    } catch {
        return null;
    }
}

function componentCounts(components: Array<{ type?: string }> | undefined): Record<string, number> {
    if (!components || components.length === 0) return {};
    const counts: Record<string, number> = {};
    for (const comp of components) {
        const t = comp.type || "agent";
        counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
}

export interface BuildPlanCardProps {
    /** Artifact filename — used to look up content from global artifacts and fetch on completion. */
    filename: string;
    /** True once the artifact has finished streaming. */
    isComplete: boolean;
}

/**
 * Renders a build manifest artifact as a compact plan card.
 * During streaming, uses accumulatedContent from the global artifact state.
 * On completion, fetches the real artifact content from the backend (same
 * pattern as ArtifactMessage) so it survives artifact refetches.
 */
export const BuildPlanCard: React.FC<BuildPlanCardProps> = ({ filename, isComplete }) => {
    const { artifacts, downloadAndResolveArtifact } = useChatContext();
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const isFetchingRef = useRef(false);

    const artifact = useMemo(() => artifacts.find(a => a.filename === filename), [artifacts, filename]);

    // During streaming, use accumulatedContent; once fetched, use fetchedContent
    const content = fetchedContent ?? artifact?.accumulatedContent ?? "";

    // When complete, fetch the real content from the backend
    useEffect(() => {
        if (!isComplete || fetchedContent || isFetchingRef.current) return;
        isFetchingRef.current = true;

        downloadAndResolveArtifact(filename)
            .then(fileData => {
                if (fileData?.content) {
                    try {
                        const binary = atob(fileData.content);
                        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
                        setFetchedContent(new TextDecoder().decode(bytes));
                    } catch {
                        setFetchedContent(fileData.content);
                    }
                }
            })
            .catch(err => {
                console.error(`[BuildPlanCard] Failed to fetch ${filename}:`, err);
            })
            .finally(() => {
                isFetchingRef.current = false;
            });
    }, [isComplete, fetchedContent, filename, downloadAndResolveArtifact]);

    const manifest = useMemo(() => parsePartialManifest(content, isComplete), [content, isComplete]);

    const counts = useMemo(() => componentCounts(manifest?.components), [manifest?.components]);
    const hasComponents = Object.keys(counts).length > 0;
    const name = manifest?.display_name || manifest?.name;

    return (
        <div
            className="flex min-w-[280px] max-w-[420px] flex-col gap-2 rounded-lg border px-4 py-3"
            style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}
        >
            {/* Header row: spinner (if streaming) + title */}
            <div className="flex items-center gap-2.5">
                {!isComplete && <Spinner size="small" variant="primary" />}
                <span className="truncate text-sm font-semibold">
                    {!isComplete
                        ? name ? `Creating build plan: ${name}` : "Creating build plan..."
                        : name || "Build Plan"}
                </span>
            </div>

            {/* Description */}
            {manifest?.description && (
                <p className="text-muted-foreground line-clamp-2 text-xs leading-relaxed">
                    {manifest.description}
                </p>
            )}

            {/* Component icons with counts */}
            {hasComponents && (
                <div className="text-muted-foreground flex items-center gap-3 pt-0.5">
                    {COMPONENT_TYPE_ORDER.filter(t => counts[t]).map(t => {
                        const Icon = COMPONENT_ICON_MAP[t] || Bot;
                        return (
                            <span
                                key={t}
                                className="flex items-center gap-1"
                                title={`${counts[t]} ${t}${counts[t] > 1 ? "s" : ""}`}
                            >
                                <Icon className="h-3.5 w-3.5" />
                                {counts[t] > 1 && <span className="text-[10px]">{counts[t]}</span>}
                            </span>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
