import { describe, test, expect } from "vitest";
import { SamFeatureProvider } from "./SamFeatureProvider";

describe("SamFeatureProvider", () => {
    describe("metadata", () => {
        test("has the correct provider name", () => {
            const provider = new SamFeatureProvider({});
            expect(provider.metadata.name).toBe("SamFeatureProvider");
        });

        test("runs on client", () => {
            const provider = new SamFeatureProvider({});
            expect(provider.runsOn).toBe("client");
        });
    });

    describe("initialize", () => {
        test("resolves without error", async () => {
            const provider = new SamFeatureProvider({});
            await expect(provider.initialize()).resolves.toBeUndefined();
        });
    });

    describe("resolveBooleanEvaluation", () => {
        test("returns true flag value with STATIC reason when key is known", () => {
            const provider = new SamFeatureProvider({ my_feature: true });
            const result = provider.resolveBooleanEvaluation("my_feature", false);
            expect(result).toEqual({ value: true, reason: "STATIC" });
        });

        test("returns false flag value with STATIC reason when key is known", () => {
            const provider = new SamFeatureProvider({ my_feature: false });
            const result = provider.resolveBooleanEvaluation("my_feature", true);
            expect(result).toEqual({ value: false, reason: "STATIC" });
        });

        test("returns default value with DEFAULT reason when key is missing", () => {
            const provider = new SamFeatureProvider({});
            expect(provider.resolveBooleanEvaluation("unknown", true)).toEqual({ value: true, reason: "DEFAULT" });
            expect(provider.resolveBooleanEvaluation("unknown", false)).toEqual({ value: false, reason: "DEFAULT" });
        });

        test("returns defaults for all lookups when flags dict is empty", () => {
            const provider = new SamFeatureProvider({});
            expect(provider.resolveBooleanEvaluation("any_flag", true)).toEqual({ value: true, reason: "DEFAULT" });
        });
    });

    describe("resolveStringEvaluation", () => {
        test("returns default value with DEFAULT reason", () => {
            const provider = new SamFeatureProvider({ my_flag: true });
            expect(provider.resolveStringEvaluation("my_flag", "fallback")).toEqual({ value: "fallback", reason: "DEFAULT" });
        });
    });

    describe("resolveNumberEvaluation", () => {
        test("returns default value with DEFAULT reason", () => {
            const provider = new SamFeatureProvider({ my_flag: true });
            expect(provider.resolveNumberEvaluation("my_flag", 42)).toEqual({ value: 42, reason: "DEFAULT" });
        });
    });

    describe("resolveObjectEvaluation", () => {
        test("returns default value with DEFAULT reason", () => {
            const provider = new SamFeatureProvider({ my_flag: true });
            const defaultVal = { key: "value" };
            expect(provider.resolveObjectEvaluation("my_flag", defaultVal)).toEqual({ value: defaultVal, reason: "DEFAULT" });
        });
    });

    describe("constructor defensive copy", () => {
        test("mutating the input map does not affect the provider", () => {
            const input: Record<string, boolean> = { my_feature: true };
            const provider = new SamFeatureProvider(input);

            input["my_feature"] = false;

            expect(provider.resolveBooleanEvaluation("my_feature", false)).toEqual({ value: true, reason: "STATIC" });
        });

        test("adding keys to input map after construction does not affect provider", () => {
            const input: Record<string, boolean> = {};
            const provider = new SamFeatureProvider(input);

            input["new_flag"] = true;

            expect(provider.resolveBooleanEvaluation("new_flag", false)).toEqual({ value: false, reason: "DEFAULT" });
        });
    });
});
