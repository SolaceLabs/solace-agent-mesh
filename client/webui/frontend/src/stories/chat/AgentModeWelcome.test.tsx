/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { AgentModeWelcome } from "@/lib/components/chat/AgentModeWelcome";

expect.extend(matchers);

describe("AgentModeWelcome", () => {
    test("renders the provided message, falling back to the default when absent or empty", () => {
        const { rerender } = render(<AgentModeWelcome message="Ask me anything" />);
        expect(screen.getByText("Ask me anything")).toBeInTheDocument();

        rerender(<AgentModeWelcome message="" />);
        expect(screen.getByText("How can I help?")).toBeInTheDocument();

        rerender(<AgentModeWelcome />);
        expect(screen.getByText("How can I help?")).toBeInTheDocument();
    });
});
