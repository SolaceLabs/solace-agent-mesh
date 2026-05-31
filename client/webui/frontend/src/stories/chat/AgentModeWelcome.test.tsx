/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { AgentModeWelcome } from "@/lib/components/chat/AgentModeWelcome";

expect.extend(matchers);

describe("AgentModeWelcome", () => {
    test("renders the default prompt when no message is provided", () => {
        render(<AgentModeWelcome />);

        expect(screen.getByText("How can I help?")).toBeInTheDocument();
    });

    test("renders the provided message instead of the default", () => {
        render(<AgentModeWelcome message="Ask me anything" />);

        expect(screen.getByText("Ask me anything")).toBeInTheDocument();
        expect(screen.queryByText("How can I help?")).not.toBeInTheDocument();
    });

    test("falls back to the default prompt for an empty message", () => {
        render(<AgentModeWelcome message="" />);

        expect(screen.getByText("How can I help?")).toBeInTheDocument();
    });
});
