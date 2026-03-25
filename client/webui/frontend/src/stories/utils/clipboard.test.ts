import { describe, test, expect, vi, beforeEach } from "vitest";
import { copyToClipboard, copyDeferredToClipboard } from "@/lib/utils/clipboard";

describe("copyToClipboard", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    test("returns true on successful copy", async () => {
        Object.assign(navigator, {
            clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
        });
        const result = await copyToClipboard("hello");
        expect(result).toBe(true);
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith("hello");
    });

    test("returns false when clipboard API fails", async () => {
        Object.assign(navigator, {
            clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
        });
        const result = await copyToClipboard("hello");
        expect(result).toBe(false);
    });
});

describe("copyDeferredToClipboard", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    test("returns true when deferred copy succeeds", async () => {
        const mockWrite = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, { clipboard: { write: mockWrite } });
        // Mock ClipboardItem globally
        vi.stubGlobal(
            "ClipboardItem",
            class {
                items: Record<string, Promise<Blob>>;
                constructor(items: Record<string, Promise<Blob>>) {
                    this.items = items;
                }
            }
        );

        const result = await copyDeferredToClipboard(Promise.resolve("deferred text"));
        expect(result).toBe(true);
        expect(mockWrite).toHaveBeenCalled();
    });

    test("returns false when ClipboardItem constructor throws", async () => {
        vi.stubGlobal("ClipboardItem", undefined);
        const result = await copyDeferredToClipboard(Promise.resolve("text"));
        expect(result).toBe(false);
    });
});
