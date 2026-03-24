import { describe, it, expect } from "vitest";
import { createSemaphore } from "./semaphore";

describe("createSemaphore", () => {
    it("acquire resolves immediately when slots are available", async () => {
        const { acquire } = createSemaphore(2);
        // Both should resolve immediately (no queuing)
        await acquire();
        await acquire();
    });

    it("acquire queues when all slots are taken", async () => {
        const { acquire, release } = createSemaphore(1);
        await acquire(); // takes the only slot

        let resolved = false;
        const pending = acquire().then(() => {
            resolved = true;
        });

        // Give microtasks a chance to flush
        await Promise.resolve();
        expect(resolved).toBe(false);

        release(); // free the slot — should transfer to the queued waiter
        await pending;
        expect(resolved).toBe(true);
    });

    it("release transfers a slot to the next queued waiter", async () => {
        const { acquire, release } = createSemaphore(1);
        await acquire();

        const order: number[] = [];
        const p1 = acquire().then(() => {
            order.push(1);
        });
        const p2 = acquire().then(() => {
            order.push(2);
        });

        release(); // transfers to first waiter
        await p1;
        release(); // transfers to second waiter
        await p2;

        expect(order).toEqual([1, 2]);
    });

    it("acquireOrAbort returns false when the signal is already aborted", async () => {
        const { acquireOrAbort } = createSemaphore(2);
        const controller = new AbortController();
        controller.abort();

        const result = await acquireOrAbort(controller.signal);
        expect(result).toBe(false);
    });

    it("acquireOrAbort returns true when slots are available and signal is not aborted", async () => {
        const { acquireOrAbort } = createSemaphore(2);
        const controller = new AbortController();

        const result = await acquireOrAbort(controller.signal);
        expect(result).toBe(true);
    });

    it("queued waiter is cleaned up when signal is aborted before slot is granted", async () => {
        const { acquire, release, acquireOrAbort } = createSemaphore(1);
        await acquire(); // take the only slot

        const controller = new AbortController();
        const pending = acquireOrAbort(controller.signal);

        // Abort while still queued — should remove from queue and resolve false
        controller.abort();
        const result = await pending;
        expect(result).toBe(false);

        // The slot should still be held by the first acquire — release it
        release();

        // A new acquire should succeed immediately (no leaked slots)
        const controller2 = new AbortController();
        const result2 = await acquireOrAbort(controller2.signal);
        expect(result2).toBe(true);
    });

    it("does not leak a slot when abort races with slot grant", async () => {
        const { acquire, release, acquireOrAbort } = createSemaphore(1);
        await acquire(); // take the only slot

        const controller = new AbortController();
        const pending = acquireOrAbort(controller.signal);

        // Release the slot (transfers to the queued waiter) and abort simultaneously
        controller.abort();
        release();

        const result = await pending;
        expect(result).toBe(false);

        // The slot must not be leaked — a new acquire should work
        const controller2 = new AbortController();
        const result2 = await acquireOrAbort(controller2.signal);
        expect(result2).toBe(true);
    });
});
