/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ShareNotification } from "@/lib/components/chat/ShareNotification";

expect.extend(matchers);

const RECENT_TIMESTAMP = Date.now() - 30_000; // 30 seconds ago

describe("ShareNotification", () => {
    test("renders user-specific share message", () => {
        render(<ShareNotification sharedBy="Alice" shareType="user-specific" sharedWith="Bob" sharedAt={RECENT_TIMESTAMP} />);

        expect(screen.getByText("Alice")).toBeInTheDocument();
        expect(screen.getByText("Bob")).toBeInTheDocument();
        expect(screen.getByText(/shared this chat with/)).toBeInTheDocument();
    });

    test("renders domain-restricted share message", () => {
        render(<ShareNotification sharedBy="Alice" shareType="domain-restricted" sharedAt={RECENT_TIMESTAMP} />);

        expect(screen.getByText("Alice")).toBeInTheDocument();
        expect(screen.getByText("your domain")).toBeInTheDocument();
    });

    test("renders authenticated share message", () => {
        render(<ShareNotification sharedBy="Alice" shareType="authenticated" sharedAt={RECENT_TIMESTAMP} />);

        expect(screen.getByText("authenticated users")).toBeInTheDocument();
    });

    test("renders public link share message", () => {
        render(<ShareNotification sharedBy="Alice" shareType="public" sharedAt={RECENT_TIMESTAMP} />);

        expect(screen.getByText("public link")).toBeInTheDocument();
    });

    test("displays relative timestamp", () => {
        const { container } = render(<ShareNotification sharedBy="Alice" shareType="public" sharedAt={RECENT_TIMESTAMP} />);

        // Should show a relative time like "30s ago"
        const timeEl = container.querySelector("p.text-muted-foreground\\/70");
        expect(timeEl?.textContent).toMatch(/\d+s ago/);
    });
});
