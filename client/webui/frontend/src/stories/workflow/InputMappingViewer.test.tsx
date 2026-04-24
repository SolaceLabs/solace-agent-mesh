/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import InputMappingViewer from "@/lib/components/workflowVisualization/InputMappingViewer";

expect.extend(matchers);

describe("InputMappingViewer", () => {
    test("renders empty-state message when mapping is null (guards Object.entries)", () => {
        render(<InputMappingViewer mapping={null as unknown as Record<string, unknown>} />);
        expect(screen.getByText(/No input mapping defined/i)).toBeInTheDocument();
    });

    test("renders empty-state message when mapping is undefined", () => {
        render(<InputMappingViewer mapping={undefined as unknown as Record<string, unknown>} />);
        expect(screen.getByText(/No input mapping defined/i)).toBeInTheDocument();
    });

    test("renders empty-state message when mapping is {}", () => {
        render(<InputMappingViewer mapping={{}} />);
        expect(screen.getByText(/No input mapping defined/i)).toBeInTheDocument();
    });

    test("renders mapping entries when values are primitives", () => {
        render(<InputMappingViewer mapping={{ alpha: "one", beta: 42, gamma: true }} />);
        expect(screen.getByText("alpha")).toBeInTheDocument();
        expect(screen.getByText("beta")).toBeInTheDocument();
        expect(screen.getByText("gamma")).toBeInTheDocument();
    });

    test("handles nested object whose inner value is null (guards Object.entries recursion)", () => {
        // Ensures MappingValue's null-object guard at line 102 doesn't throw.
        const mapping: Record<string, unknown> = {
            wrapper: { innerNull: null, innerNumber: 7 },
        };
        render(<InputMappingViewer mapping={mapping} />);
        expect(screen.getByText("wrapper")).toBeInTheDocument();
    });
});
