/// <reference types="@testing-library/jest-dom" />
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import { useSortableTable } from "@/lib/components/ui/hooks/useSortableTable";

const mockData = [
    { name: "charlie", score: 30 },
    { name: "alice", score: 25 },
    { name: "bob", score: 35 },
];

describe("useSortableTable", () => {
    test("defaults to first column ascending", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        expect(result.current.sortKey).toBe("name");
        expect(result.current.sortDir).toBe("asc");
    });

    test("sorts data by first column ascending on init", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        const names = result.current.sortedData.map(d => d.name);
        expect(names).toEqual(["alice", "bob", "charlie"]);
    });

    test("toggles to descending when clicking the active column", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        act(() => result.current.handleSort("name"));
        expect(result.current.sortDir).toBe("desc");
        const names = result.current.sortedData.map(d => d.name);
        expect(names).toEqual(["charlie", "bob", "alice"]);
    });

    test("toggles back to ascending on a second click of the same column", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        act(() => result.current.handleSort("name"));
        act(() => result.current.handleSort("name"));
        expect(result.current.sortDir).toBe("asc");
    });

    test("resets to ascending when switching to a new column", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        act(() => result.current.handleSort("name"));
        act(() => result.current.handleSort("score"));
        expect(result.current.sortKey).toBe("score");
        expect(result.current.sortDir).toBe("asc");
        const scores = result.current.sortedData.map(d => d.score);
        expect(scores).toEqual([25, 30, 35]);
    });

    test("returns empty array unchanged for empty input", () => {
        const { result } = renderHook(() => useSortableTable([], ["name", "score"]));
        expect(result.current.sortedData).toEqual([]);
    });

    test("does not mutate the original data array", () => {
        const data = [
            { name: "charlie", score: 30 },
            { name: "alice", score: 25 },
        ];
        const snapshot = JSON.stringify(data);
        renderHook(() => useSortableTable(data, ["name", "score"]));
        expect(JSON.stringify(data)).toBe(snapshot);
    });

    test("sorts numeric values lexicographically as strings", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["score", "name"]));
        // String comparison: "25" < "30" < "35" — matches numeric order for these values
        const scores = result.current.sortedData.map(d => d.score);
        expect(scores).toEqual([25, 30, 35]);
    });

    test("sorts descending correctly after switching columns", () => {
        const { result } = renderHook(() => useSortableTable(mockData, ["name", "score"]));
        act(() => result.current.handleSort("score"));
        act(() => result.current.handleSort("score"));
        expect(result.current.sortDir).toBe("desc");
        const scores = result.current.sortedData.map(d => d.score);
        expect(scores).toEqual([35, 30, 25]);
    });

    test("updates sorted output when data prop changes", () => {
        let data = [{ name: "zara", score: 1 }];
        const { result, rerender } = renderHook(() => useSortableTable(data, ["name", "score"]));
        expect(result.current.sortedData[0].name).toBe("zara");

        data = [{ name: "anna", score: 2 }, { name: "zara", score: 1 }];
        rerender();
        expect(result.current.sortedData[0].name).toBe("anna");
    });
});
