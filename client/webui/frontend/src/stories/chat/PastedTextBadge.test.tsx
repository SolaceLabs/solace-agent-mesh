/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { PastedTextBadge, PendingPastedTextBadge } from "@/lib/components/chat/paste/PastedTextBadge";

expect.extend(matchers);

describe("PastedTextBadge", () => {
    test("renders the pasted text index label", () => {
        render(<PastedTextBadge index={1} textPreview="hello" onClick={vi.fn()} />);
        expect(screen.getByText("Pasted Text #1")).toBeInTheDocument();
    });

    test("shows remove button when onRemove is provided; clicking remove calls onRemove, not onClick", () => {
        const onClick = vi.fn();
        const onRemove = vi.fn();
        render(<PastedTextBadge index={2} textPreview="hi" onClick={onClick} onRemove={onRemove} />);
        const removeBtn = screen.getByTitle("Remove pasted text");
        fireEvent.click(removeBtn);
        expect(onRemove).toHaveBeenCalledTimes(1);
        expect(onClick).not.toHaveBeenCalled();
    });
});

describe("PendingPastedTextBadge", () => {
    test("shows default filename label when not configured", () => {
        render(<PendingPastedTextBadge content="some text" onClick={vi.fn()} onRemove={vi.fn()} isConfigured={false} defaultFilename="snippet.txt" />);
        expect(screen.getByText("snippet.txt")).toBeInTheDocument();
    });

    test("shows configured filename with blue badge when isConfigured is true", () => {
        render(<PendingPastedTextBadge content="some text" onClick={vi.fn()} onRemove={vi.fn()} isConfigured={true} filename="report.txt" />);
        expect(screen.getByText("report.txt")).toBeInTheDocument();
    });
});
