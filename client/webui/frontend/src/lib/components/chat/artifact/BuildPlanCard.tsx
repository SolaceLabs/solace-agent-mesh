import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Bot, BookOpen, CheckCircle2, ChevronDown, ChevronRight, Circle, FlaskConical, Globe, Loader2, Pencil, Plug, Workflow, X } from "lucide-react";
import yaml from "js-yaml";

import { Button } from "@/lib/components/ui";
import { Spinner } from "@/lib/components/ui/spinner";
import { useChatContext } from "@/lib/hooks";

/** Prevent event from bubbling up to parent form elements */
function stopPropagation(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
}

/** Full manifest structure for rendering and editing. */
interface BuildManifest {
    name?: string;
    display_name?: string;
    description?: string;
    components?: BuildManifestComponent[];
}

interface BuildManifestComponent {
    filename?: string;
    type?: string;
    name?: string;
    status?: string;
    origin?: string;
    gateway_type?: string;
    connector_type?: string;
    connector_subtype?: string;
    depends_on?: string[];
}

const COMPONENT_TYPE_ORDER = ["gateway", "workflow", "agent", "skill", "connector"] as const;
const COMPONENT_ICON_MAP: Record<string, typeof Bot> = {
    workflow: Workflow,
    connector: Plug,
    gateway: Globe,
    skill: BookOpen,
    agent: Bot,
};
const COMPONENT_TYPE_LABELS: Record<string, string> = {
    gateway: "Gateway",
    workflow: "Workflow",
    agent: "Agent",
    skill: "Skill",
    connector: "Connector",
};

/**
 * Trims partial streaming YAML to the last complete line (ending with \n)
 * so that yaml.load() doesn't choke on a half-written value.
 * Once `isComplete` is true, the full content is used as-is.
 */
export function trimToCompleteYaml(raw: string, isComplete: boolean): string {
    if (isComplete) return raw;
    const lastNewline = raw.lastIndexOf("\n");
    if (lastNewline <= 0) return "";
    return raw.slice(0, lastNewline + 1);
}

export function parseManifest(raw: string, isComplete: boolean): BuildManifest | null {
    const trimmed = trimToCompleteYaml(raw, isComplete);
    if (!trimmed) return null;
    try {
        const doc = yaml.load(trimmed);
        if (!doc || typeof doc !== "object") return null;
        return doc as BuildManifest;
    } catch {
        return null;
    }
}

function componentCounts(components: BuildManifestComponent[] | undefined): Record<string, number> {
    if (!components || components.length === 0) return {};
    const counts: Record<string, number> = {};
    for (const comp of components) {
        const t = comp.type || "agent";
        counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
}

/**
 * Determine the primary testable target from a manifest.
 * Prefers the first workflow (top-level orchestration), then the first agent.
 */
function getTestTarget(manifest: BuildManifest | null): { name: string; type: "agent" | "workflow"; displayName: string } | null {
    if (!manifest?.components) return null;
    const sessionComponents = manifest.components.filter(c => c.origin !== "platform");
    const workflow = sessionComponents.find(c => c.type === "workflow");
    if (workflow?.name) return { name: workflow.name, type: "workflow", displayName: manifest.display_name || workflow.name };
    const agent = sessionComponents.find(c => c.type === "agent");
    if (agent?.name) return { name: agent.name, type: "agent", displayName: manifest.display_name || agent.name };
    return null;
}

export interface BuildPlanCardProps {
    /** Artifact filename — used to look up content from global artifacts and fetch on completion. */
    filename: string;
    /** True once the artifact has finished streaming. */
    isComplete: boolean;
    /** Callback when user clicks "Build & Activate" — sends approval to proceed */
    onBuildActivate?: (manifest: BuildManifest) => void;
    /** Callback when user clicks "Keep Editing" — prompts AI to ask what to change */
    onKeepEditing?: () => void;
    /** Callback when user edits the plan and submits changes */
    onPlanEdited?: (editSummary: string) => void;
    /** Hide action buttons (Edit Plan, Keep Editing, Build & Activate) — e.g. when a follow-up question is pending */
    hideActions?: boolean;
    /** Whether the parent message is complete — when false and artifact is complete, shows "Building..." state */
    isMessageComplete?: boolean;
    /**
     * Called when the user clicks the "Test" button after build completion.
     * Receives the target agent/workflow name, its type, and a display name.
     * If not provided, the Test button is not shown.
     */
    onTestRequest?: (targetName: string, targetType: "agent" | "workflow", displayName: string) => void;
}

/**
 * Renders a build manifest artifact as a "Suggested Action Plan" card.
 *
 * During streaming: shows compact card with spinner and component counts.
 * On completion: shows full plan with description, component list,
 * "Edit Plan" link, and "Keep Editing" / "Build & Activate" buttons.
 */
export const BuildPlanCard: React.FC<BuildPlanCardProps> = ({ filename, isComplete, onBuildActivate, onKeepEditing, onPlanEdited, hideActions = false, isMessageComplete = true, onTestRequest }) => {
    const { artifacts, downloadAndResolveArtifact, handleSubmit, isResponding, builderMode, displayError } = useChatContext();
    // When builderMode is true, we're in the dedicated builder page which has its own
    // InlinePlanCard with approve/request changes flow. Keep the community BuildPlanCard
    // compact to avoid conflicting with the enterprise approval flow.
    // builderMode is only true on the /builder page — regular chat never sets it.
    const isEnterpriseBuilder = builderMode;
    const [fetchedContent, setFetchedContent] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [planExpanded, setPlanExpanded] = useState(false);
    const [editedManifest, setEditedManifest] = useState<BuildManifest | null>(null);
    const [actioned, setActioned] = useState(false);
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
                displayError({ title: "Failed to load build plan", error: err instanceof Error ? err.message : `Could not fetch ${filename}.` });
            })
            .finally(() => {
                isFetchingRef.current = false;
            });
    }, [isComplete, fetchedContent, filename, downloadAndResolveArtifact]);

    const manifest = useMemo(() => parseManifest(content, isComplete), [content, isComplete]);

    const counts = useMemo(() => componentCounts(manifest?.components), [manifest?.components]);
    const hasComponents = Object.keys(counts).length > 0;
    const name = manifest?.display_name || manifest?.name;

    // Initialize edited manifest when entering edit mode
    const handleEditPlan = useCallback(() => {
        if (manifest) {
            setEditedManifest(JSON.parse(JSON.stringify(manifest)));
            setIsEditing(true);
        }
    }, [manifest]);

    const handleCancelEdit = useCallback(() => {
        setIsEditing(false);
        setEditedManifest(null);
    }, []);

    const handleSaveEdit = useCallback(() => {
        if (!editedManifest || !manifest) return;

        // Build a summary of changes
        const changes: string[] = [];
        if (editedManifest.name !== manifest.name) {
            changes.push(`Renamed project to "${editedManifest.name}"`);
        }
        if (editedManifest.description !== manifest.description) {
            changes.push(`Updated description`);
        }

        // Check for removed components
        const originalNames = new Set(manifest.components?.map(c => c.name) || []);
        const editedNames = new Set(editedManifest.components?.map(c => c.name) || []);
        for (const n of originalNames) {
            if (n && !editedNames.has(n)) {
                changes.push(`Removed component "${n}"`);
            }
        }

        const summary = changes.length > 0 ? `I'd like to make these changes to the plan:\n${changes.map(c => `- ${c}`).join("\n")}` : "I've reviewed the plan and it looks good.";

        setIsEditing(false);
        setEditedManifest(null);

        if (onPlanEdited) {
            onPlanEdited(summary);
        } else {
            // Fallback: send as a chat message
            const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
            handleSubmit(fakeEvent, null, summary);
        }
    }, [editedManifest, manifest, onPlanEdited, handleSubmit]);

    const handleBuildActivate = useCallback(() => {
        setActioned(true);
        if (onBuildActivate && manifest) {
            onBuildActivate(manifest);
        } else {
            // Send approval with a styled displayHtml chip instead of raw text.
            // The actual message text is sent to the agent; displayHtml controls what the user sees.
            const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
            const displayChip = `<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:6px;font-size:13px;font-weight:500;opacity:0.7">✅ Plan approved</span>`;
            handleSubmit(fakeEvent, null, "Build it.", null, displayChip);
        }
    }, [onBuildActivate, manifest, handleSubmit]);

    const handleKeepEditing = useCallback(() => {
        setActioned(true);
        if (onKeepEditing) {
            onKeepEditing();
        } else {
            const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
            const displayChip = `<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;border-radius:6px;font-size:13px;font-weight:500;opacity:0.7">✏️ Editing plan</span>`;
            handleSubmit(fakeEvent, null, "I'd like to make some changes to this plan.", null, displayChip);
        }
    }, [onKeepEditing, handleSubmit]);

    const handleRemoveComponent = useCallback(
        (index: number) => {
            if (!editedManifest?.components) return;
            setEditedManifest(prev => {
                if (!prev?.components) return prev;
                const updated = { ...prev, components: [...prev.components] };
                updated.components.splice(index, 1);
                return updated;
            });
        },
        [editedManifest]
    );

    // Determine the test target from the manifest
    const testTarget = useMemo(() => getTestTarget(manifest), [manifest]);

    // ─── Enterprise Builder: render nothing ───────────────────────────
    // Enterprise has its own InlinePlanCard with approve/request changes flow.
    // The community BuildPlanCard is completely hidden to avoid duplicate plan displays.
    if (isEnterpriseBuilder) {
        return null;
    }

    // ─── Streaming / Planning Phase ───────────────────────────────────
    if (!isComplete) {
        return (
            <div className="flex max-w-[420px] min-w-[280px] flex-col gap-2 rounded-lg border px-4 py-3" style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}>
                <div className="flex items-center gap-2.5">
                    <Spinner size="small" variant="primary" />
                    <span className="truncate text-sm font-semibold">{name ? `Creating build plan: ${name}` : "Creating build plan..."}</span>
                </div>
                {manifest?.description && <p className="text-muted-foreground line-clamp-2 text-xs leading-relaxed">{manifest.description}</p>}
                {hasComponents && (
                    <div className="text-muted-foreground flex items-center gap-3 pt-0.5">
                        {COMPONENT_TYPE_ORDER.filter(t => counts[t]).map(t => {
                            const Icon = COMPONENT_ICON_MAP[t] || Bot;
                            return (
                                <span key={t} className="flex items-center gap-1" title={`${counts[t]} ${t}${counts[t] > 1 ? "s" : ""}`}>
                                    <Icon className="h-3.5 w-3.5" />
                                    {counts[t] > 1 && <span className="text-[10px]">{counts[t]}</span>}
                                </span>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    }

    // ─── Edit Mode ────────────────────────────────────────────────────
    if (isEditing && editedManifest) {
        return (
            <div className="flex w-[480px] max-w-full flex-col gap-3 rounded-lg border px-5 py-4" style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}>
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Pencil className="text-muted-foreground h-4 w-4" />
                        <span className="text-sm font-semibold">Edit Action Plan</span>
                    </div>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={e => {
                            stopPropagation(e);
                            handleCancelEdit();
                        }}
                    >
                        <X className="h-3.5 w-3.5" />
                    </Button>
                </div>

                {/* Editable project name */}
                <div>
                    <label className="text-muted-foreground mb-1 block text-xs font-medium">Project Name</label>
                    <input
                        type="text"
                        className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm focus:ring-1 focus:ring-(--primary-wMain) focus:outline-none"
                        value={editedManifest.name || ""}
                        onChange={e => setEditedManifest(prev => (prev ? { ...prev, name: e.target.value } : prev))}
                    />
                </div>

                {/* Editable description */}
                <div>
                    <label className="text-muted-foreground mb-1 block text-xs font-medium">Description</label>
                    <textarea
                        className="w-full resize-none rounded-md border bg-transparent px-3 py-1.5 text-sm focus:ring-1 focus:ring-(--primary-wMain) focus:outline-none"
                        rows={3}
                        value={editedManifest.description || ""}
                        onChange={e => setEditedManifest(prev => (prev ? { ...prev, description: e.target.value } : prev))}
                    />
                </div>

                {/* Editable components */}
                {editedManifest.components && editedManifest.components.length > 0 && (
                    <div>
                        <label className="text-muted-foreground mb-2 block text-xs font-medium">Components</label>
                        <div className="flex flex-col gap-2">
                            {editedManifest.components.map((comp, idx) => {
                                const Icon = COMPONENT_ICON_MAP[comp.type || "agent"] || Bot;
                                return (
                                    <div key={idx} className="flex items-center gap-2 rounded-md border px-3 py-2">
                                        <Icon className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                                        <span className="min-w-0 flex-1 truncate text-sm">{comp.name || "Unnamed"}</span>
                                        <span className="text-muted-foreground text-xs">{COMPONENT_TYPE_LABELS[comp.type || "agent"]}</span>
                                        <button
                                            type="button"
                                            className="text-muted-foreground hover:text-destructive ml-1 flex-shrink-0 transition-colors"
                                            onClick={e => {
                                                stopPropagation(e);
                                                handleRemoveComponent(idx);
                                            }}
                                            title="Remove component"
                                        >
                                            <X className="h-3.5 w-3.5" />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Save / Cancel buttons */}
                <div className="flex items-center justify-end gap-2 pt-1">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                            stopPropagation(e);
                            handleCancelEdit();
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        variant="default"
                        size="sm"
                        onClick={e => {
                            stopPropagation(e);
                            handleSaveEdit();
                        }}
                    >
                        Submit Changes
                    </Button>
                </div>
            </div>
        );
    }

    // ─── Complete: Suggested Action Plan ──────────────────────────────
    // Determine if the agent is actively building:
    // 1. Same message still streaming (artifact done, message not done)
    // 2. OR: builder mode + global isResponding (Phase 3 running in subsequent messages)
    //    AND the user has already actioned (clicked Build & Activate)
    const isActivelyBuilding = isComplete && !isEditing && (!isMessageComplete || (builderMode && isResponding && actioned));

    const displayComponents = manifest?.components || [];
    // Sort components by type order for consistent display
    const sortedComponents = [...displayComponents].sort((a, b) => {
        const aIdx = COMPONENT_TYPE_ORDER.indexOf((a.type || "agent") as (typeof COMPONENT_TYPE_ORDER)[number]);
        const bIdx = COMPONENT_TYPE_ORDER.indexOf((b.type || "agent") as (typeof COMPONENT_TYPE_ORDER)[number]);
        return (aIdx === -1 ? 99 : aIdx) - (bIdx === -1 ? 99 : bIdx);
    });

    // ─── Actioned: "Approved Action Plan" + Building Timeline ─────────
    // After user clicks "Build & Activate", show collapsible approved plan
    // header + vertical timeline of component creation progress
    if (actioned) {
        return (
            <div className="flex flex-col gap-3">
                {/* Collapsible "Approved Action Plan" header — same pattern as InlineProgressUpdates */}
                <div className="flex items-center gap-2">
                    <Button
                        type="button"
                        variant="ghost"
                        className="flex items-center gap-1 text-sm text-(--secondary-text-wMain) transition-colors hover:text-(--primary-text-wMain)"
                        onClick={e => {
                            stopPropagation(e);
                            setPlanExpanded(!planExpanded);
                        }}
                    >
                        {planExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span className="font-medium">Approved Action Plan</span>
                    </Button>
                </div>

                {/* Expanded plan details */}
                {planExpanded && (
                    <div className="ml-6 flex w-[480px] max-w-full flex-col gap-2 rounded-lg border px-4 py-3" style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}>
                        {manifest?.description && <p className="text-muted-foreground text-sm leading-relaxed">{manifest.description}</p>}
                        {sortedComponents.length > 0 && (
                            <div className="text-muted-foreground flex flex-wrap items-center gap-3 pt-0.5">
                                {COMPONENT_TYPE_ORDER.filter(t => sortedComponents.some(c => c.type === t)).map(t => {
                                    const Icon = COMPONENT_ICON_MAP[t] || Bot;
                                    const count = sortedComponents.filter(c => c.type === t).length;
                                    return (
                                        <span key={t} className="flex items-center gap-1" title={`${count} ${t}${count > 1 ? "s" : ""}`}>
                                            <Icon className="h-3.5 w-3.5" />
                                            <span className="text-xs">
                                                {count} {COMPONENT_TYPE_LABELS[t] || t}
                                                {count > 1 ? "s" : ""}
                                            </span>
                                        </span>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}

                {/* Building timeline — vertical dots + connecting line, same pattern as InlineProgressUpdates */}
                {isActivelyBuilding && (
                    <div>
                        <div className="mb-1 px-2 py-1 text-sm font-medium text-(--secondary-text-wMain)">Creating...</div>
                        <div className="relative">
                            {/* Vertical connecting line */}
                            {sortedComponents.length > 1 && <div className="absolute top-[21px] left-[9px] z-0 w-[2px] rounded-full bg-current opacity-30" style={{ bottom: "21px" }} />}
                            {sortedComponents.map((comp, idx) => {
                                const Icon = COMPONENT_ICON_MAP[comp.type || "agent"] || Bot;
                                const isLast = idx === sortedComponents.length - 1;
                                // Without builder_component_progress events, show all as "in progress"
                                // The last component gets the spinner, others get green dots (optimistic)
                                const showSpinner = isLast;
                                return (
                                    <div
                                        key={idx}
                                        className="flex items-start gap-3 py-2"
                                        style={{
                                            animation: "progressSlideIn 0.3s ease-out both",
                                            animationDelay: `${Math.min(idx * 50, 200)}ms`,
                                        }}
                                    >
                                        {/* Dot or spinner indicator */}
                                        <div className="relative z-10 flex h-5 w-5 flex-shrink-0 items-center justify-center">
                                            {showSpinner ? <Loader2 className="h-[14px] w-[14px] animate-spin text-(--primary-wMain)" /> : <div className="h-[10px] w-[10px] rounded-full bg-(--success-wMain)" />}
                                        </div>
                                        {/* Component info */}
                                        <div className="flex min-w-0 items-center gap-1.5">
                                            <Icon className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
                                            <span className={`text-sm leading-relaxed ${showSpinner ? "text-(--primary-text-wMain)" : "text-(--secondary-text-wMain)"}`}>{comp.name || "Unnamed"}</span>
                                            <span className="text-muted-foreground text-xs">{COMPONENT_TYPE_LABELS[comp.type || "agent"]}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Completed state — all done, with optional Test button */}
                {!isActivelyBuilding && (
                    <div className="flex items-center gap-3 px-2">
                        <span className="text-muted-foreground text-xs italic">All components created.</span>
                        {onTestRequest && testTarget && !isResponding && (
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="gap-1.5 text-xs"
                                onClick={e => {
                                    stopPropagation(e);
                                    onTestRequest(testTarget.name, testTarget.type, testTarget.displayName);
                                }}
                            >
                                <FlaskConical className="h-3 w-3" />
                                Test {testTarget.type === "workflow" ? "Workflow" : "Agent"}
                            </Button>
                        )}
                    </div>
                )}
            </div>
        );
    }

    // ─── Not actioned: Suggested Action Plan with buttons ─────────────
    return (
        <div className="flex w-[480px] max-w-full flex-col gap-3 rounded-lg border px-5 py-4" style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}>
            {/* Header: "Suggested Action Plan" + "Edit Plan" link */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <Circle className="text-muted-foreground h-5 w-5" />
                    <span className="text-sm font-semibold">Suggested Action Plan</span>
                </div>
                {!hideActions && (
                    <button
                        type="button"
                        className="flex items-center gap-1 text-sm font-medium text-(--primary-wMain) transition-colors hover:opacity-80"
                        onClick={e => {
                            stopPropagation(e);
                            handleEditPlan();
                        }}
                    >
                        <Pencil className="h-3.5 w-3.5" />
                        Edit Plan
                    </button>
                )}
            </div>

            {/* Plan description */}
            {manifest?.description && <p className="text-muted-foreground text-sm leading-relaxed">{manifest.description}</p>}

            {/* Components section */}
            {sortedComponents.length > 0 && (
                <div>
                    <h4 className="text-muted-foreground mb-2 text-xs font-semibold tracking-wide uppercase">Components</h4>
                    <div className="flex flex-col gap-2">
                        {sortedComponents.map((comp, idx) => {
                            const Icon = COMPONENT_ICON_MAP[comp.type || "agent"] || Bot;
                            return (
                                <div key={idx} className="flex items-center gap-3 rounded-md border px-3 py-2.5" style={{ borderColor: "var(--secondary-w8040)" }}>
                                    <Circle className="text-muted-foreground h-4 w-4 flex-shrink-0 opacity-50" />
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                                            <Icon className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
                                            <span className="truncate text-sm font-medium">{comp.name || "Unnamed"}</span>
                                        </div>
                                        {comp.type && (
                                            <span className="text-muted-foreground text-xs">
                                                {COMPONENT_TYPE_LABELS[comp.type] || comp.type}
                                                {comp.connector_type && ` · ${comp.connector_type}`}
                                                {comp.gateway_type && ` · ${comp.gateway_type}`}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Action buttons: "Keep Editing" + "Build & Activate" */}
            {!hideActions && (
                <div className="flex items-center justify-end gap-3 pt-1">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-sm font-medium"
                        onClick={e => {
                            stopPropagation(e);
                            handleKeepEditing();
                        }}
                    >
                        Keep Editing
                    </Button>
                    <Button
                        type="button"
                        variant="default"
                        size="sm"
                        onClick={e => {
                            stopPropagation(e);
                            handleBuildActivate();
                        }}
                    >
                        Build &amp; Activate
                    </Button>
                </div>
            )}
        </div>
    );
};
