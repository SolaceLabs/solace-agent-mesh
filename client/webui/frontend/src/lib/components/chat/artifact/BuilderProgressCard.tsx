/**
 * BuilderProgressCard
 *
 * Renders a compact progress card showing the creation state of each builder
 * component during the build process. Replaces BuildPlanCard when the builder
 * is actively creating components (i.e., builderCreationState.isBuilding is true).
 *
 * Each component row shows:
 * - Queued: gray circle outline
 * - Active: animated spinner
 * - Completed: green checkmark
 * - Failed: red X circle
 * - Skipped: gray dash
 * - Input Required: amber pause icon
 *
 * Skills in active state show an optional progress bar.
 */

import React, { useMemo } from "react";
import { Bot, BookOpen, CheckCircle2, Circle, CirclePause, Globe, Loader2, MinusCircle, Plug, Workflow, XCircle } from "lucide-react";

import type { BuilderComponentProgress, BuilderComponentState } from "@/lib/types/builder";

/** Ordered list of component types for display grouping */
const COMPONENT_TYPE_ORDER = ["gateway", "workflow", "agent", "skill", "connector"] as const;

/** Human-readable labels for component types */
const COMPONENT_TYPE_LABELS: Record<string, string> = {
    gateway: "Gateway",
    workflow: "Workflow",
    agent: "Agent",
    skill: "Skill",
    connector: "Connector",
};

/** Icon mapping for component types */
const COMPONENT_ICON_MAP: Record<string, typeof Bot> = {
    workflow: Workflow,
    connector: Plug,
    gateway: Globe,
    skill: BookOpen,
    agent: Bot,
};

/** State indicator icon component */
function StateIcon({ state, className = "h-4 w-4" }: { state: BuilderComponentState; className?: string }) {
    switch (state) {
        case "completed":
            return <CheckCircle2 className={`${className} text-green-500`} />;
        case "active":
            return <Loader2 className={`${className} animate-spin text-teal-500`} />;
        case "failed":
            return <XCircle className={`${className} text-destructive`} />;
        case "skipped":
            return <MinusCircle className={`${className} text-muted-foreground opacity-60`} />;
        case "input-required":
            return <CirclePause className={`${className} text-amber-500`} />;
        case "queued":
        default:
            return <Circle className={`${className} text-muted-foreground opacity-40`} />;
    }
}

export interface BuilderProgressCardProps {
    /** Components from BuilderCreationState */
    components: BuilderComponentProgress[];
    /** Whether the build is still in progress */
    isBuilding: boolean;
    /** Display name for the build (from manifest) */
    buildName?: string;
    /** Callback when a completed component is clicked — opens config dialog */
    onComponentClick?: (componentId: string) => void;
}

/**
 * Renders a build progress card showing each component with its creation state.
 * During building, shows spinner + "Creating: <name>".
 * After completion, shows "Build Complete: <name>" or "Build Failed".
 */
export const BuilderProgressCard: React.FC<BuilderProgressCardProps> = ({ components, isBuilding, buildName, onComponentClick }) => {
    // Group components by type in display order
    const groupedComponents = useMemo(() => {
        const groups: Array<{ type: string; items: BuilderComponentProgress[] }> = [];
        for (const type of COMPONENT_TYPE_ORDER) {
            const items = components.filter(c => c.type === type);
            if (items.length > 0) {
                groups.push({ type, items });
            }
        }
        return groups;
    }, [components]);

    // Compute summary stats
    const completedCount = components.filter(c => c.state === "completed").length;
    const totalCount = components.length;
    const hasFailed = components.some(c => c.state === "failed");
    const activeComponent = components.find(c => c.state === "active" || c.state === "input-required");

    // Header text
    const headerText = useMemo(() => {
        if (isBuilding) {
            return buildName ? `Creating: ${buildName}` : "Creating components...";
        }
        if (hasFailed) {
            return buildName ? `Build failed: ${buildName}` : "Build failed";
        }
        return buildName ? `Build complete: ${buildName}` : "Build complete";
    }, [isBuilding, hasFailed, buildName]);

    return (
        <div className="flex max-w-[480px] min-w-[300px] flex-col gap-2 rounded-lg border px-4 py-3" style={{ backgroundColor: "var(--background-w10)", borderColor: "var(--secondary-w8040)" }}>
            {/* Header row: spinner/checkmark + title */}
            <div className="flex items-center gap-2.5">
                {isBuilding ? <Loader2 className="h-4 w-4 animate-spin text-teal-500" /> : hasFailed ? <XCircle className="text-destructive h-4 w-4" /> : <CheckCircle2 className="h-4 w-4 text-green-500" />}
                <span className="truncate text-sm font-semibold">{headerText}</span>
            </div>

            {/* Progress summary */}
            {totalCount > 0 && (
                <div className="flex items-center gap-2">
                    <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
                        <div className="h-full rounded-full bg-green-500 transition-all duration-500 ease-out" style={{ width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%` }} />
                    </div>
                    <span className="text-muted-foreground text-xs">
                        {completedCount}/{totalCount}
                    </span>
                </div>
            )}

            {/* Component list grouped by type */}
            <div className="flex flex-col gap-1">
                {groupedComponents.map(group =>
                    group.items.map(component => {
                        const TypeIcon = COMPONENT_ICON_MAP[component.type] || Bot;
                        const isClickable = component.state === "completed" && !!onComponentClick;
                        const isActive = component.state === "active" || component.state === "input-required";

                        return (
                            <div
                                key={component.id}
                                className={`flex items-start gap-2 rounded-md px-2 py-1.5 transition-colors ${isClickable ? "hover:bg-muted/50 cursor-pointer" : ""} ${isActive ? "bg-muted/30" : ""}`}
                                onClick={isClickable ? () => onComponentClick(component.id) : undefined}
                                role={isClickable ? "button" : undefined}
                                tabIndex={isClickable ? 0 : undefined}
                                onKeyDown={
                                    isClickable
                                        ? e => {
                                              if (e.key === "Enter" || e.key === " ") {
                                                  e.preventDefault();
                                                  onComponentClick(component.id);
                                              }
                                          }
                                        : undefined
                                }
                            >
                                {/* State indicator */}
                                <div className="mt-0.5 flex-shrink-0">
                                    <StateIcon state={component.state} />
                                </div>

                                {/* Component info */}
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-1.5">
                                        <TypeIcon className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
                                        <span className={`truncate text-sm ${component.state === "queued" || component.state === "skipped" ? "text-muted-foreground" : ""}`}>{component.name}</span>
                                        <span className="text-muted-foreground text-xs">{COMPONENT_TYPE_LABELS[component.type] || component.type}</span>
                                    </div>

                                    {/* Status text for active/input-required components */}
                                    {isActive && component.statusText && <p className="text-muted-foreground mt-0.5 truncate text-xs">{component.statusText}</p>}

                                    {/* Progress bar for skills with progressPercent */}
                                    {component.state === "active" && component.type === "skill" && component.progressPercent != null && (
                                        <div className="bg-muted mt-1 h-1 overflow-hidden rounded-full">
                                            <div className="h-full rounded-full bg-teal-500 transition-all duration-300 ease-out" style={{ width: `${component.progressPercent}%` }} />
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            {/* Current activity text at bottom */}
            {isBuilding && activeComponent && !activeComponent.statusText && <p className="text-muted-foreground truncate text-xs">{activeComponent.state === "input-required" ? "Waiting for input..." : `Working on ${activeComponent.name}...`}</p>}
        </div>
    );
};
