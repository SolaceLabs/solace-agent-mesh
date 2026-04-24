/**
 * Session-local store of deep-research plan_ids the user has already responded
 * to (or that the backend has marked stale). Exists because the server's SSE
 * stream can re-deliver the original `deep_research_plan` data part on
 * reconnect / full event replay; without this store the resurrected event
 * would replace the message in state with a fresh copy that has no
 * `responded` flag, resurrecting a card the user has already acted on.
 *
 * Scope is intentionally module-level (in-memory, per-tab) - responses do not
 * need to survive reloads since on reload the backend task has either moved
 * on or finished, and a fresh plan card for any still-open research is fine.
 */

export type RespondedAction = "start" | "cancel" | "stale";

const respondedPlans = new Map<string, RespondedAction>();
const listeners = new Set<() => void>();

export function markPlanResponded(planId: string, action: RespondedAction) {
    respondedPlans.set(planId, action);
    listeners.forEach(listener => listener());
}

export function subscribeRespondedPlans(listener: () => void) {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

export function getRespondedPlansSnapshot(): ReadonlyMap<string, RespondedAction> {
    return respondedPlans;
}

export function __resetRespondedPlansForTest() {
    respondedPlans.clear();
    listeners.forEach(listener => listener());
}
