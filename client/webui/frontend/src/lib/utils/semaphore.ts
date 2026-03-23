/**
 * Creates a simple concurrency limiter (semaphore).
 *
 * Returns `acquire` and `release` functions that limit the number of
 * concurrent operations to `maxConcurrency`.  When all slots are in use,
 * `acquire()` returns a promise that resolves once a slot becomes available.
 */
export function createSemaphore(maxConcurrency: number) {
    let active = 0;
    const queue: Array<() => void> = [];

    function acquire(): Promise<void> {
        if (active < maxConcurrency) {
            active++;
            return Promise.resolve();
        }
        return new Promise<void>(resolve => {
            queue.push(resolve);
        });
    }

    function release(): void {
        if (queue.length > 0) {
            const next = queue.shift()!;
            // Keep `active` the same — the slot is transferred to the next waiter
            next();
        } else {
            active--;
        }
    }

    /**
     * Acquire a slot with abort-signal awareness.
     * Returns `true` if a slot was acquired (caller must release).
     * Returns `false` if the signal was already aborted or became aborted while queued.
     * In the `false` case no slot is held — the caller must not call `release`.
     */
    function acquireOrAbort(signal: AbortSignal): Promise<boolean> {
        if (signal.aborted) return Promise.resolve(false);

        if (active < maxConcurrency) {
            active++;
            return Promise.resolve(true);
        }

        return new Promise<boolean>(resolve => {
            const onAbort = () => {
                const idx = queue.indexOf(grantSlot);
                if (idx !== -1) {
                    queue.splice(idx, 1);
                    resolve(false);
                } else {
                    // Slot was already transferred to us — give it back
                    release();
                    resolve(false);
                }
            };

            const grantSlot = () => {
                signal.removeEventListener("abort", onAbort);
                if (signal.aborted) {
                    release();
                    resolve(false);
                } else {
                    resolve(true);
                }
            };

            queue.push(grantSlot);
            signal.addEventListener("abort", onAbort, { once: true });
        });
    }

    return { acquire, release, acquireOrAbort };
}
