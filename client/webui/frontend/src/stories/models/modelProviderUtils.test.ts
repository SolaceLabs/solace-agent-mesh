import { describe, it, expect } from "vitest";
import { coerceCustomParamValue, formatCustomParamValue } from "../../lib/components/models/modelProviderUtils";

describe("coerceCustomParamValue", () => {
    it("parses unquoted numbers as numbers", () => {
        expect(coerceCustomParamValue("500")).toBe(500);
        expect(coerceCustomParamValue("3.14")).toBe(3.14);
        expect(coerceCustomParamValue("-42")).toBe(-42);
        expect(coerceCustomParamValue("0")).toBe(0);
    });

    it("parses quoted numbers as strings", () => {
        expect(coerceCustomParamValue('"500"')).toBe("500");
        expect(coerceCustomParamValue('"3.14"')).toBe("3.14");
    });

    it("parses unquoted booleans as booleans", () => {
        expect(coerceCustomParamValue("true")).toBe(true);
        expect(coerceCustomParamValue("false")).toBe(false);
    });

    it("parses quoted booleans as strings", () => {
        expect(coerceCustomParamValue('"true"')).toBe("true");
        expect(coerceCustomParamValue('"false"')).toBe("false");
    });

    it("parses unquoted null as null", () => {
        expect(coerceCustomParamValue("null")).toBeNull();
    });

    it("parses quoted null as string", () => {
        expect(coerceCustomParamValue('"null"')).toBe("null");
    });

    it("treats plain unquoted text as a string", () => {
        expect(coerceCustomParamValue("hello")).toBe("hello");
        expect(coerceCustomParamValue("gpt-4o-mini")).toBe("gpt-4o-mini");
    });

    it("treats quoted text as a string", () => {
        expect(coerceCustomParamValue('"hello"')).toBe("hello");
    });

    it("treats invalid JSON as a plain string", () => {
        expect(coerceCustomParamValue("{broken")).toBe("{broken");
        expect(coerceCustomParamValue("TRUE")).toBe("TRUE");
    });
});

describe("formatCustomParamValue", () => {
    it("formats numbers unquoted", () => {
        expect(formatCustomParamValue(500)).toBe("500");
        expect(formatCustomParamValue(3.14)).toBe("3.14");
        expect(formatCustomParamValue(0)).toBe("0");
    });

    it("formats booleans unquoted", () => {
        expect(formatCustomParamValue(true)).toBe("true");
        expect(formatCustomParamValue(false)).toBe("false");
    });

    it("formats null unquoted", () => {
        expect(formatCustomParamValue(null)).toBe("null");
    });

    it("formats plain strings without quotes", () => {
        expect(formatCustomParamValue("hello")).toBe("hello");
        expect(formatCustomParamValue("gpt-4o-mini")).toBe("gpt-4o-mini");
    });

    it("quotes strings that would otherwise parse as non-string JSON", () => {
        expect(formatCustomParamValue("500")).toBe('"500"');
        expect(formatCustomParamValue("true")).toBe('"true"');
        expect(formatCustomParamValue("false")).toBe('"false"');
        expect(formatCustomParamValue("null")).toBe('"null"');
        expect(formatCustomParamValue("3.14")).toBe('"3.14"');
    });
});

describe("round-trip between coerce and format", () => {
    const cases: Array<{ stored: unknown; displayed: string }> = [
        { stored: 500, displayed: "500" },
        { stored: 3.14, displayed: "3.14" },
        { stored: true, displayed: "true" },
        { stored: false, displayed: "false" },
        { stored: null, displayed: "null" },
        { stored: "hello", displayed: "hello" },
        { stored: "500", displayed: '"500"' },
        { stored: "true", displayed: '"true"' },
    ];

    it.each(cases)("stored $stored displays as $displayed and coerces back to the same value", ({ stored, displayed }) => {
        expect(formatCustomParamValue(stored)).toBe(displayed);
        expect(coerceCustomParamValue(displayed)).toStrictEqual(stored);
    });
});
