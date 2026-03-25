import { describe, test, expect } from "vitest";
import { parseTaskMetadata, extractRagDataFromTasks } from "@/lib/utils/taskUtils";

describe("parseTaskMetadata", () => {
    test("returns null for falsy values", () => {
        expect(parseTaskMetadata(null)).toBeNull();
        expect(parseTaskMetadata(undefined)).toBeNull();
        expect(parseTaskMetadata("")).toBeNull();
        expect(parseTaskMetadata(0)).toBeNull();
    });

    test("returns the object directly when given an object", () => {
        const obj = { rag_data: [], feedback: { type: "up" } };
        expect(parseTaskMetadata(obj)).toBe(obj);
    });

    test("parses valid JSON strings", () => {
        const json = '{"rag_data": [{"query": "test"}], "agent_name": "myAgent"}';
        const result = parseTaskMetadata(json);
        expect(result).toEqual({ rag_data: [{ query: "test" }], agent_name: "myAgent" });
    });

    test("returns null for invalid JSON strings", () => {
        expect(parseTaskMetadata("{invalid json}")).toBeNull();
        expect(parseTaskMetadata("not json at all")).toBeNull();
    });

    test("returns null for non-string, non-object types", () => {
        expect(parseTaskMetadata(42)).toBeNull();
        expect(parseTaskMetadata(true)).toBeNull();
    });
});

describe("extractRagDataFromTasks", () => {
    test("returns empty array for empty tasks", () => {
        expect(extractRagDataFromTasks([])).toEqual([]);
    });

    test("extracts RAG data from tasks with object metadata", () => {
        const tasks = [
            {
                taskId: "task-1",
                taskMetadata: {
                    rag_data: [
                        { query: "search1", results: ["r1"] },
                        { query: "search2", results: ["r2"] },
                    ],
                },
            },
        ];
        const result = extractRagDataFromTasks(tasks);
        expect(result).toHaveLength(2);
        expect(result[0]).toEqual({ query: "search1", results: ["r1"], taskId: "task-1" });
        expect(result[1]).toEqual({ query: "search2", results: ["r2"], taskId: "task-1" });
    });

    test("extracts RAG data from tasks with JSON string metadata", () => {
        const tasks = [
            {
                taskId: "task-2",
                taskMetadata: JSON.stringify({ rag_data: [{ query: "q1" }] }),
            },
        ];
        const result = extractRagDataFromTasks(tasks);
        expect(result).toHaveLength(1);
        expect(result[0].taskId).toBe("task-2");
    });

    test("prefers workflowTaskId over taskId over id", () => {
        const tasks = [
            { workflowTaskId: "wf-1", taskId: "task-1", id: "id-1", taskMetadata: { rag_data: [{ q: 1 }] } },
            { taskId: "task-2", id: "id-2", taskMetadata: { rag_data: [{ q: 2 }] } },
            { id: "id-3", taskMetadata: { rag_data: [{ q: 3 }] } },
        ];
        const result = extractRagDataFromTasks(tasks);
        expect(result[0].taskId).toBe("wf-1");
        expect(result[1].taskId).toBe("task-2");
        expect(result[2].taskId).toBe("id-3");
    });

    test("skips tasks with no rag_data", () => {
        const tasks = [
            { taskId: "t1", taskMetadata: { feedback: { type: "up" } } },
            { taskId: "t2", taskMetadata: null },
            { taskId: "t3", taskMetadata: { rag_data: [{ q: "found" }] } },
        ];
        const result = extractRagDataFromTasks(tasks);
        expect(result).toHaveLength(1);
        expect(result[0].taskId).toBe("t3");
    });

    test("skips tasks with invalid JSON metadata", () => {
        const tasks = [{ taskId: "t1", taskMetadata: "{bad json}" }];
        const result = extractRagDataFromTasks(tasks);
        expect(result).toEqual([]);
    });

    test("skips tasks where rag_data is not an array", () => {
        const tasks = [{ taskId: "t1", taskMetadata: { rag_data: "not-array" as unknown as unknown[] } }];
        const result = extractRagDataFromTasks(tasks);
        expect(result).toEqual([]);
    });
});
