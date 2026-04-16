import { describe, it, expect } from "vitest";
import { getByPath, setByPath, resolveContext } from "./A2UIRenderer";

describe("getByPath", () => {
    it("reads a top-level key", () => {
        expect(getByPath({ foo: "bar" }, "/foo")).toBe("bar");
    });

    it("reads a nested key", () => {
        expect(getByPath({ a: { b: { c: 42 } } }, "/a/b/c")).toBe(42);
    });

    it("returns undefined for missing path", () => {
        expect(getByPath({ a: 1 }, "/b")).toBeUndefined();
    });

    it("returns undefined for partially missing nested path", () => {
        expect(getByPath({ a: { b: 1 } }, "/a/c/d")).toBeUndefined();
    });

    it("handles path without leading slash", () => {
        expect(getByPath({ foo: "bar" }, "foo")).toBe("bar");
    });

    it("reads from arrays by index", () => {
        expect(getByPath({ items: ["a", "b", "c"] } as Record<string, unknown>, "/items/1")).toBe("b");
    });

    it("returns undefined when traversing through a non-object", () => {
        expect(getByPath({ a: "string" }, "/a/b")).toBeUndefined();
    });

    it("returns undefined when traversing through null", () => {
        expect(getByPath({ a: null } as Record<string, unknown>, "/a/b")).toBeUndefined();
    });

    it("reads falsy values correctly", () => {
        expect(getByPath({ a: 0 }, "/a")).toBe(0);
        expect(getByPath({ a: false }, "/a")).toBe(false);
        expect(getByPath({ a: "" }, "/a")).toBe("");
        expect(getByPath({ a: null } as Record<string, unknown>, "/a")).toBeNull();
    });
});

describe("setByPath", () => {
    it("sets a top-level key", () => {
        const result = setByPath({}, "/foo", "bar");
        expect(result).toEqual({ foo: "bar" });
    });

    it("sets a nested key", () => {
        const result = setByPath({}, "/a/b/c", 42);
        expect(result).toEqual({ a: { b: { c: 42 } } });
    });

    it("does not mutate the original model", () => {
        const original = { a: { b: 1 } };
        const result = setByPath(original, "/a/b", 2);
        expect(original.a.b).toBe(1);
        expect(result.a).toEqual({ b: 2 });
    });

    it("overwrites an existing value", () => {
        const result = setByPath({ a: { b: "old" } }, "/a/b", "new");
        expect(result).toEqual({ a: { b: "new" } });
    });

    it("creates intermediate objects when they don't exist", () => {
        const result = setByPath({ x: 1 }, "/a/b/c", "deep");
        expect(result).toEqual({ x: 1, a: { b: { c: "deep" } } });
    });

    it("overwrites non-object intermediate values", () => {
        const result = setByPath({ a: "string" }, "/a/b", "value");
        expect(result).toEqual({ a: { b: "value" } });
    });
});

describe("resolveContext", () => {
    it("resolves path references from the model", () => {
        const model = { answers: { q0: "yes", q1: "no" } };
        const context = {
            answer: { path: "/answers/q0" },
            static: "literal",
        };
        const result = resolveContext(context, model);
        expect(result).toEqual({ answer: "yes", static: "literal" });
    });

    it("returns undefined for missing path references", () => {
        const model = { a: 1 };
        const context = { val: { path: "/missing" } };
        const result = resolveContext(context, model);
        expect(result).toEqual({ val: undefined });
    });

    it("passes through non-path objects unchanged", () => {
        const model = {};
        const context = { config: { key: "value" } };
        const result = resolveContext(context, model);
        expect(result).toEqual({ config: { key: "value" } });
    });

    it("passes through primitive values", () => {
        const model = {};
        const context = { num: 42, str: "hello", bool: true, nil: null } as Record<string, unknown>;
        const result = resolveContext(context, model);
        expect(result).toEqual({ num: 42, str: "hello", bool: true, nil: null });
    });

    it("resolves multiple path references", () => {
        const model = { x: 10, y: 20 };
        const context = {
            a: { path: "/x" },
            b: { path: "/y" },
        };
        const result = resolveContext(context, model);
        expect(result).toEqual({ a: 10, b: 20 });
    });
});
