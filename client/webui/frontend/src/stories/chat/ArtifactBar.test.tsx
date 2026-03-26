/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ArtifactBar } from "@/lib/components/chat/artifact/ArtifactBar";

expect.extend(matchers);

describe("ArtifactBar primaryLabel logic", () => {
    test("shows description as primary label when provided", () => {
        render(<ArtifactBar filename="report.pdf" description="Monthly sales report" status="completed" />);
        // Description is the primary (bold) label
        expect(screen.getByText("Monthly sales report")).toBeInTheDocument();
        // Filename still appears in the secondary line, but description is the prominent label
        const primaryLabel = screen.getByTitle("Monthly sales report");
        expect(primaryLabel).toBeInTheDocument();
    });

    test("shows filename when no description and filename is ≤50 chars", () => {
        render(<ArtifactBar filename="short-name.pdf" status="completed" />);
        expect(screen.getByText("short-name.pdf")).toBeInTheDocument();
    });

    test("truncates filename to 47 chars + ellipsis when >50 chars and no description", () => {
        const longName = "this-is-a-very-long-filename-that-exceeds-fifty-characters.pdf";
        render(<ArtifactBar filename={longName} status="completed" />);
        const expected = `${longName.substring(0, 47)}...`;
        expect(screen.getByText(expected)).toBeInTheDocument();
    });
});

describe("ArtifactBar keyboard accessibility", () => {
    test("pressing Enter on a completed+previewable bar calls onPreview", () => {
        const onPreview = vi.fn();
        render(
            <ArtifactBar
                filename="report.pdf"
                status="completed"
                actions={{ onPreview }}
            />
        );
        const bar = screen.getByRole("button");
        fireEvent.keyDown(bar, { key: "Enter" });
        expect(onPreview).toHaveBeenCalledTimes(1);
    });

    test("pressing Space on a completed+previewable bar calls onPreview", () => {
        const onPreview = vi.fn();
        render(
            <ArtifactBar
                filename="report.pdf"
                status="completed"
                actions={{ onPreview }}
            />
        );
        const bar = screen.getByRole("button");
        fireEvent.keyDown(bar, { key: " " });
        expect(onPreview).toHaveBeenCalledTimes(1);
    });

    test("in-progress bar has no role=button and no keyboard handler", () => {
        render(<ArtifactBar filename="report.pdf" status="in-progress" />);
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    test("deleted completed bar has no role=button", () => {
        const onPreview = vi.fn();
        render(
            <ArtifactBar
                filename="report.pdf"
                status="completed"
                actions={{ onPreview }}
                isDeleted
            />
        );
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });
});