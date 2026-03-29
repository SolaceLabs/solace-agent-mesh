import { describe, test, expect } from "vitest";
import { getUserInitials, formatCollaborativeTimestamp } from "@/lib/utils/userFormatting";

describe("getUserInitials", () => {
    test("returns two-letter initials from first and last name", () => {
        expect(getUserInitials("John Doe")).toBe("JD");
    });

    test("returns first two chars for single name", () => {
        expect(getUserInitials("Alice")).toBe("AL");
    });

    test("uses first and last name for three-word names", () => {
        expect(getUserInitials("Vincent Van Gogh")).toBe("VG");
    });

    test("returns empty string for empty input", () => {
        expect(getUserInitials("")).toBe("");
    });

    test("returns empty string for whitespace-only input", () => {
        expect(getUserInitials("   ")).toBe("");
    });

    test("uppercases the initials", () => {
        expect(getUserInitials("jane smith")).toBe("JS");
    });
});

describe("formatCollaborativeTimestamp", () => {
    test("formats epoch timestamp as time string", () => {
        // Use a fixed timestamp: 2024-01-15 14:30:00 UTC
        const ts = new Date("2024-01-15T14:30:00Z").getTime();
        const result = formatCollaborativeTimestamp(ts);
        // Should contain colon-separated time with AM/PM
        expect(result).toMatch(/\d{1,2}:\d{2}\s*(AM|PM)/i);
    });
});
