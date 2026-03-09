/**
 * Generic A2UI v0.9 surface renderer.
 *
 * Renders a flat adjacency-list of A2UI components as a React component tree.
 * No knowledge of specific surface shapes (approval, question, etc.) — it
 * renders whatever the backend sends.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { AlertTriangle, Clock } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Card, CardContent } from "@/lib/components/ui/card";
import { Checkbox } from "@/lib/components/ui/checkbox";
import { Input } from "@/lib/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/lib/components/ui/tabs";
import type { A2UIComponent, A2UISurface } from "@/lib/types";

import type { SurfaceAction } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract literal string from A2UI text field. */
function lit(val: unknown): string {
    if (typeof val === "string") return val;
    if (val && typeof val === "object" && "literalString" in val) {
        return String((val as { literalString: string }).literalString);
    }
    return "";
}

/** Build a lookup map from component ID → component. */
function buildIndex(components: A2UIComponent[]): Map<string, A2UIComponent> {
    const map = new Map<string, A2UIComponent>();
    for (const c of components) {
        if (c.id) map.set(c.id, c);
    }
    return map;
}

/** Get the children IDs from a component's children field. */
function getChildrenIds(comp: A2UIComponent): string[] {
    const children = comp.children as { explicitList?: string[] } | undefined;
    if (children?.explicitList) return children.explicitList;
    // Single child.
    if (typeof comp.child === "string") return [comp.child];
    return [];
}

/** Read a value from the data model by JSON pointer path (e.g. "/answers/q0"). */
function getByPath(model: Record<string, unknown>, path: string): unknown {
    const parts = path.replace(/^\//, "").split("/");
    let current: unknown = model;
    for (const part of parts) {
        if (current && typeof current === "object" && part in (current as Record<string, unknown>)) {
            current = (current as Record<string, unknown>)[part];
        } else {
            return undefined;
        }
    }
    return current;
}

/** Set a value in the data model by JSON pointer path. Returns a new model (immutable). */
function setByPath(model: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
    const parts = path.replace(/^\//, "").split("/");
    const clone = structuredClone(model);
    let current: Record<string, unknown> = clone;
    for (let i = 0; i < parts.length - 1; i++) {
        if (!(parts[i] in current) || typeof current[parts[i]] !== "object") {
            current[parts[i]] = {};
        }
        current = current[parts[i]] as Record<string, unknown>;
    }
    current[parts[parts.length - 1]] = value;
    return clone;
}

/** Resolve action context — replace {path: "/..."} refs with data model values. */
function resolveContext(context: Record<string, unknown>, model: Record<string, unknown>): Record<string, unknown> {
    const resolved: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(context)) {
        if (val && typeof val === "object" && "path" in val) {
            resolved[key] = getByPath(model, (val as { path: string }).path);
        } else {
            resolved[key] = val;
        }
    }
    return resolved;
}

// ---------------------------------------------------------------------------
// Component Renderers
// ---------------------------------------------------------------------------

interface RenderCtx {
    index: Map<string, A2UIComponent>;
    model: Record<string, unknown>;
    onModelChange: (model: Record<string, unknown>) => void;
    onAction: (action: SurfaceAction) => void;
    disabled: boolean;
}

function RenderComponent({ id, ctx }: { id: string; ctx: RenderCtx }) {
    const comp = ctx.index.get(id);
    if (!comp) return null;

    switch (comp.component) {
        case "Card":
            return <RenderCard comp={comp} ctx={ctx} />;
        case "Column":
            return <RenderColumn comp={comp} ctx={ctx} />;
        case "Row":
            return <RenderRow comp={comp} ctx={ctx} />;
        case "Text":
            return <RenderText comp={comp} />;
        case "Icon":
            return <RenderIcon comp={comp} />;
        case "ChoicePicker":
            return <RenderChoicePicker comp={comp} ctx={ctx} />;
        case "TextField":
            return <RenderTextField comp={comp} ctx={ctx} />;
        case "Button":
            return <RenderButton comp={comp} ctx={ctx} />;
        case "Tabs":
            return <RenderTabs comp={comp} ctx={ctx} />;
        default:
            return null;
    }
}

function RenderChildren({ ids, ctx }: { ids: string[]; ctx: RenderCtx }) {
    return (
        <>
            {ids.map(id => (
                <RenderComponent key={id} id={id} ctx={ctx} />
            ))}
        </>
    );
}

function RenderCard({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const childIds = getChildrenIds(comp);
    return (
        <Card className="w-full gap-0 py-0" noPadding>
            <CardContent noPadding>
                <RenderChildren ids={childIds} ctx={ctx} />
            </CardContent>
        </Card>
    );
}

function RenderColumn({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const childIds = getChildrenIds(comp);
    return (
        <div className="flex flex-col gap-3 px-4 py-3">
            <RenderChildren ids={childIds} ctx={ctx} />
        </div>
    );
}

function RenderRow({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const childIds = getChildrenIds(comp);
    const justify = comp.justify === "end" ? "justify-end" : "justify-start";
    return (
        <div className={`flex items-center gap-2 ${justify}`}>
            <RenderChildren ids={childIds} ctx={ctx} />
        </div>
    );
}

function RenderText({ comp }: { comp: A2UIComponent }) {
    const text = lit(comp.text);
    const variant = comp.variant as string | undefined;

    switch (variant) {
        case "h3":
            return <span className="text-sm font-semibold">{text}</span>;
        case "caption":
            return <span className="text-xs text-muted-foreground">{text}</span>;
        case "body":
        default:
            return <span className="text-sm">{text}</span>;
    }
}

function RenderIcon({ comp }: { comp: A2UIComponent }) {
    const icon = comp.icon as string;
    switch (icon) {
        case "warning":
            return <AlertTriangle className="size-5 text-[var(--color-warning-wMain)]" />;
        default:
            return <span className="size-5" />;
    }
}

function RenderChoicePicker({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const variant = comp.variant as string;
    const isMulti = variant === "multipleSelection";
    const rawOptions = Array.isArray(comp.options) ? (comp.options as Record<string, unknown>[]) : [];
    const valuePath = (comp.value as { path?: string })?.path ?? "";
    const currentValue = valuePath ? getByPath(ctx.model, valuePath) : undefined;

    const options = rawOptions.map(o => ({
        label: lit(o.label),
        value: String(o.value ?? ""),
        description: o.description ? lit(o.description) : undefined,
    }));

    const handleSingleSelect = (val: string) => {
        if (valuePath) ctx.onModelChange(setByPath(ctx.model, valuePath, val));
    };

    const handleMultiToggle = (val: string, checked: boolean) => {
        const current = Array.isArray(currentValue) ? (currentValue as string[]) : [];
        const updated = checked ? [...current, val] : current.filter(v => v !== val);
        if (valuePath) ctx.onModelChange(setByPath(ctx.model, valuePath, updated));
    };

    return (
        <div className="space-y-1">
            {options.map(opt =>
                isMulti ? (
                    <label
                        key={opt.value}
                        className="flex cursor-pointer items-start gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted/50"
                    >
                        <Checkbox
                            checked={Array.isArray(currentValue) && currentValue.includes(opt.value)}
                            onCheckedChange={(checked: boolean) => handleMultiToggle(opt.value, checked)}
                            disabled={ctx.disabled}
                            className="mt-0.5"
                        />
                        <div className="min-w-0">
                            <span>{opt.label}</span>
                            {opt.description && <p className="text-xs text-muted-foreground">{opt.description}</p>}
                        </div>
                    </label>
                ) : (
                    <label
                        key={opt.value}
                        className={`flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2 text-sm transition-colors ${
                            currentValue === opt.value
                                ? "border-[var(--color-brand-wMain)] bg-[var(--color-brand-wMain)]/5"
                                : "border-transparent hover:bg-muted/50"
                        }`}
                    >
                        <input
                            type="radio"
                            name={comp.id}
                            value={opt.value}
                            checked={currentValue === opt.value}
                            onChange={() => handleSingleSelect(opt.value)}
                            disabled={ctx.disabled}
                            className="mt-0.5 size-4 accent-[var(--color-primary-wMain)]"
                        />
                        <div className="min-w-0">
                            <span>{opt.label}</span>
                            {opt.description && <p className="text-xs text-muted-foreground">{opt.description}</p>}
                        </div>
                    </label>
                ),
            )}
        </div>
    );
}

function RenderTextField({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const placeholder = lit(comp.placeholder);
    const valuePath = (comp.value as { path?: string })?.path ?? "";
    const currentValue = valuePath ? String(getByPath(ctx.model, valuePath) ?? "") : "";

    return (
        <Input
            placeholder={placeholder}
            value={currentValue}
            onChange={e => {
                if (valuePath) ctx.onModelChange(setByPath(ctx.model, valuePath, e.target.value));
            }}
            disabled={ctx.disabled}
        />
    );
}

function RenderButton({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const childIds = getChildrenIds(comp);
    const variant = comp.variant as string | undefined;
    const action = comp.action as {
        event?: { name?: string; context?: Record<string, unknown>; completionText?: string };
    } | undefined;
    const eventName = action?.event?.name ?? "";
    const eventContext = action?.event?.context ?? {};
    const completionText = action?.event?.completionText ?? "";

    const isCancel = eventName === "cancel";
    const isPrimary = variant === "primary";

    const handleClick = () => {
        const resolved = resolveContext(eventContext, ctx.model);
        ctx.onAction({ eventName, context: resolved, completionText });
    };

    return (
        <Button
            size="sm"
            variant={isPrimary ? "default" : isCancel ? "ghost" : "outline"}
            onClick={handleClick}
            disabled={ctx.disabled}
        >
            <RenderChildren ids={childIds} ctx={ctx} />
        </Button>
    );
}

// ---------------------------------------------------------------------------
// Tabs with auto-advance
// ---------------------------------------------------------------------------

interface TabItem {
    title: unknown;
    child: string;
}

/**
 * Check whether a tab panel should show a "Next" button instead of auto-advancing.
 *
 * Returns true when:
 * - The panel has a multipleSelection ChoicePicker (user picks many, can't auto-advance)
 * - The panel has no ChoicePicker at all (text-only tab)
 * - The panel's mutuallyExclusive picker currently has "__other__" selected
 */
function tabNeedsNextButton(panelId: string, ctx: RenderCtx): boolean {
    const panel = ctx.index.get(panelId);
    if (!panel) return false;

    const childIds = getChildrenIds(panel);
    const children = childIds.map(id => ctx.index.get(id)).filter(Boolean) as A2UIComponent[];

    const picker = children.find(c => c.component === "ChoicePicker");
    if (!picker) return true; // no picker → show Next
    if (picker.variant === "multipleSelection") return true; // multi-select → show Next

    // mutuallyExclusive: check if __other__ is currently selected.
    const pickerPath = (picker.value as { path?: string })?.path ?? "";
    const currentVal = pickerPath ? getByPath(ctx.model, pickerPath) : undefined;
    return currentVal === "__other__";
}

function RenderTabs({ comp, ctx }: { comp: A2UIComponent; ctx: RenderCtx }) {
    const tabItems = (comp.tabItems as TabItem[]) ?? [];
    const autoAdvance = comp["x-auto-advance"] === true;
    const [activeTab, setActiveTab] = useState(tabItems[0]?.child ?? "");

    // Track a pending auto-advance timer so we can cancel it if the user changes tabs manually.
    const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Wrap onModelChange to detect single-select changes and auto-advance.
    const handleModelChange = useCallback(
        (newModel: Record<string, unknown>) => {
            ctx.onModelChange(newModel);

            if (!autoAdvance) return;

            const currentIndex = tabItems.findIndex(t => t.child === activeTab);
            if (currentIndex < 0 || currentIndex >= tabItems.length - 1) return;

            // Check if the active tab's picker is mutuallyExclusive.
            const panel = ctx.index.get(activeTab);
            if (!panel) return;
            const childIds = getChildrenIds(panel);
            const picker = childIds
                .map(id => ctx.index.get(id))
                .find(c => c?.component === "ChoicePicker");

            if (!picker || picker.variant !== "mutuallyExclusive") return;

            const pickerPath = (picker.value as { path?: string })?.path ?? "";
            const newValue = pickerPath ? getByPath(newModel, pickerPath) : undefined;

            // Auto-advance if a non-empty, non-__other__ value was selected.
            if (typeof newValue === "string" && newValue !== "" && newValue !== "__other__") {
                if (advanceTimer.current) clearTimeout(advanceTimer.current);
                advanceTimer.current = setTimeout(() => {
                    setActiveTab(tabItems[currentIndex + 1].child);
                    advanceTimer.current = null;
                }, 300);
            }
        },
        [ctx, autoAdvance, activeTab, tabItems],
    );

    // Build a context with the wrapped onModelChange for child components.
    const tabCtx: RenderCtx = useMemo(
        () => ({
            ...ctx,
            onModelChange: autoAdvance ? handleModelChange : ctx.onModelChange,
        }),
        [ctx, autoAdvance, handleModelChange],
    );

    const handleTabChange = useCallback(
        (value: string) => {
            // Cancel any pending auto-advance if the user manually switches.
            if (advanceTimer.current) {
                clearTimeout(advanceTimer.current);
                advanceTimer.current = null;
            }
            setActiveTab(value);
        },
        [],
    );

    return (
        <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList>
                {tabItems.map(item => (
                    <TabsTrigger key={item.child} value={item.child}>
                        {lit(item.title)}
                    </TabsTrigger>
                ))}
            </TabsList>
            {tabItems.map((item, idx) => (
                <TabsContent key={item.child} value={item.child}>
                    <RenderComponent id={item.child} ctx={tabCtx} />
                    {autoAdvance && idx < tabItems.length - 1 && tabNeedsNextButton(item.child, tabCtx) && (
                        <div className="flex justify-end px-4 pt-2">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setActiveTab(tabItems[idx + 1].child)}
                                disabled={ctx.disabled}
                            >
                                Next
                            </Button>
                        </div>
                    )}
                </TabsContent>
            ))}
        </Tabs>
    );
}

// ---------------------------------------------------------------------------
// Top-level Surface Renderer
// ---------------------------------------------------------------------------

interface A2UISurfaceRendererProps {
    surface: A2UISurface;
    onAction: (action: SurfaceAction) => void;
    disabled?: boolean;
    expiresAt?: string;
}

export function A2UISurfaceRenderer({ surface, onAction, disabled = false, expiresAt }: A2UISurfaceRendererProps) {
    const [model, setModel] = useState<Record<string, unknown>>(() =>
        (surface.dataModel as Record<string, unknown>) ?? {},
    );

    const index = useMemo(() => buildIndex(surface.components), [surface.components]);

    const handleAction = useCallback(
        (action: SurfaceAction) => {
            onAction(action);
        },
        [onAction],
    );

    const ctx: RenderCtx = useMemo(
        () => ({
            index,
            model,
            onModelChange: setModel,
            onAction: handleAction,
            disabled,
        }),
        [index, model, handleAction, disabled],
    );

    // Find the root component — the Card with id "root".
    const rootId = surface.components.find(c => c.id === "root")?.id ?? surface.components[0]?.id;
    if (!rootId) return null;

    return (
        <div className="w-full">
            <RenderComponent id={rootId} ctx={ctx} />
            {expiresAt && <CountdownTimer expiresAt={expiresAt} />}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Countdown Timer (cosmetic)
// ---------------------------------------------------------------------------

function CountdownTimer({ expiresAt }: { expiresAt: string }) {
    const [text, setText] = useState("");

    useEffect(() => {
        const expires = new Date(expiresAt).getTime();
        if (isNaN(expires)) return;

        const update = () => {
            const remaining = expires - Date.now();
            if (remaining <= 0) {
                setText("Expired");
                return false;
            }
            const mins = Math.floor(remaining / 60000);
            const secs = Math.floor((remaining % 60000) / 1000);
            setText(mins > 0 ? `${mins}m ${secs}s` : `${secs}s`);
            return true;
        };

        if (!update()) return;
        const interval = setInterval(() => {
            if (!update()) clearInterval(interval);
        }, 1000);

        return () => clearInterval(interval);
    });

    if (!text) return null;

    return (
        <div className="flex items-center justify-center gap-1.5 py-2 text-xs text-muted-foreground">
            <Clock className="size-3" />
            <span>{text}</span>
        </div>
    );
}
