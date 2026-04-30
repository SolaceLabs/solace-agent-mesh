import { createSemaphore } from "@/lib/utils/semaphore";

/**
 * Module-level concurrency limiter for artifact preview fetches.
 *
 * Browsers typically allow ~6 concurrent connections per origin. We cap at 4
 * to leave headroom for user-initiated requests (navigation, downloads).
 *
 * Shared across the app so navigating between e.g. ArtifactsPage and the
 * chat input's attachment row does not double the connection budget.
 */
const semaphore = createSemaphore(4);

export const acquireFetchSlotOrAbort = semaphore.acquireOrAbort;
export const releaseFetchSlot = semaphore.release;

/**
 * Acquire a slot, run `fn`, and release the slot when done.
 * Returns `undefined` if the signal aborts before a slot is acquired.
 */
export async function fetchWithSlot<T>(signal: AbortSignal, fn: () => Promise<T>): Promise<T | undefined> {
    const acquired = await acquireFetchSlotOrAbort(signal);
    if (!acquired) return undefined;
    try {
        return await fn();
    } finally {
        releaseFetchSlot();
    }
}
