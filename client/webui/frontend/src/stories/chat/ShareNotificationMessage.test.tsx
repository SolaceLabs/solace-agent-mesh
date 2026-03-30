/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ShareNotificationMessage } from "@/lib/components/chat/ShareNotificationMessage";
import { TooltipProvider } from "@/lib/components/ui/tooltip";

expect.extend(matchers);

const FIXED_TIMESTAMP = new Date("2024-06-15T10:30:00Z").getTime();

const wrapper = ({ children }: { children: React.ReactNode }) => <TooltipProvider>{children}</TooltipProvider>;

describe("ShareNotificationMessage", () => {
    describe("shared-with-users variant", () => {
        test("renders viewer access for a single user", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedWith={["Alice"]} accessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/gave/)).toBeInTheDocument();
            expect(screen.getByText("Viewer")).toBeInTheDocument();
            expect(screen.getByText(/Alice/)).toBeInTheDocument();
        });

        test("renders editor access", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedWith={["Bob"]} accessLevel="editor" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText("Editor")).toBeInTheDocument();
        });

        test("defaults sharedBy to 'You'", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedWith={["Alice"]} accessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/You gave/)).toBeInTheDocument();
        });

        test("shows custom sharedBy name", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedBy="Admin" sharedWith={["Alice"]} accessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/Admin gave/)).toBeInTheDocument();
        });

        test("formats two recipients with 'and'", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedWith={["Alice", "Bob"]} accessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/Alice and Bob/)).toBeInTheDocument();
        });

        test("truncates more than 3 recipients and shows overflow count", () => {
            render(<ShareNotificationMessage variant="shared-with-users" sharedWith={["Alice", "Bob", "Charlie", "Diana", "Eve"]} accessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/2 other users/)).toBeInTheDocument();
        });
    });

    describe("role-changed variant", () => {
        test("renders role change from viewer to editor", () => {
            render(<ShareNotificationMessage variant="role-changed" sharedWith={["Alice"]} fromAccessLevel="viewer" toAccessLevel="editor" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/changed/)).toBeInTheDocument();
            expect(screen.getByText("Viewer")).toBeInTheDocument();
            expect(screen.getByText("Editor")).toBeInTheDocument();
        });

        test("renders role change from editor to viewer", () => {
            render(<ShareNotificationMessage variant="role-changed" sharedWith={["Bob"]} fromAccessLevel="editor" toAccessLevel="viewer" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText("Editor")).toBeInTheDocument();
            expect(screen.getByText("Viewer")).toBeInTheDocument();
        });
    });

    describe("created-link variant", () => {
        test("renders link creation message", () => {
            render(<ShareNotificationMessage variant="created-link" sharedBy="Admin" timestamp={FIXED_TIMESTAMP} />, { wrapper });

            expect(screen.getByText(/view-only sharing link/)).toBeInTheDocument();
        });
    });
});
