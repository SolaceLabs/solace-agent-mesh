import { describe, it, expect } from "vitest";
import { trimToCompleteYaml, parseManifest } from "./BuildPlanCard";

describe("trimToCompleteYaml", () => {
    it("returns full content when isComplete is true", () => {
        const raw = "name: test\ndescription: partial val";
        expect(trimToCompleteYaml(raw, true)).toBe(raw);
    });

    it("trims to last complete line when streaming", () => {
        const raw = "name: test\ndescription: partial";
        expect(trimToCompleteYaml(raw, false)).toBe("name: test\n");
    });

    it("returns empty string when no complete line exists", () => {
        expect(trimToCompleteYaml("no-newline-yet", false)).toBe("");
    });

    it("handles content with only a leading newline", () => {
        // lastIndexOf("\n") returns 0, which is <= 0, so returns ""
        expect(trimToCompleteYaml("\npartial", false)).toBe("");
    });

    it("handles multiple complete lines", () => {
        const raw = "name: test\nversion: 1\ncomponents:\n  - type: age";
        expect(trimToCompleteYaml(raw, false)).toBe("name: test\nversion: 1\ncomponents:\n");
    });

    it("returns empty string for empty input when streaming", () => {
        expect(trimToCompleteYaml("", false)).toBe("");
    });

    it("preserves trailing newline in complete content", () => {
        const raw = "name: test\n";
        expect(trimToCompleteYaml(raw, false)).toBe("name: test\n");
    });
});

describe("parseManifest", () => {
    it("parses valid complete YAML", () => {
        const raw = "name: my-app\ndescription: A test app\n";
        const result = parseManifest(raw, true);
        expect(result).toEqual({ name: "my-app", description: "A test app" });
    });

    it("parses streaming YAML by trimming to last complete line", () => {
        const raw = "name: my-app\ndescription: partial desc";
        const result = parseManifest(raw, false);
        expect(result).toEqual({ name: "my-app" });
    });

    it("returns null for empty streaming content", () => {
        expect(parseManifest("", false)).toBeNull();
    });

    it("returns null for non-object YAML", () => {
        expect(parseManifest("just a string\n", true)).toBeNull();
    });

    it("returns null for invalid YAML", () => {
        expect(parseManifest(":\n  :\n    : :\n", true)).toBeNull();
    });

    it("parses manifest with components array", () => {
        const raw = `name: app
components:
  - type: agent
    name: MyAgent
  - type: skill
    name: MySkill
`;
        const result = parseManifest(raw, true);
        expect(result?.name).toBe("app");
        expect(result?.components).toHaveLength(2);
        expect(result?.components?.[0]).toEqual({ type: "agent", name: "MyAgent" });
    });
});
