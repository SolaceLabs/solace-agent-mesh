/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { ModelWarningBanner } from "@/lib/components/models/ModelWarningBanner";

expect.extend(matchers);

function renderBanner(props: { showWarning: boolean; hasModelConfigWrite: boolean }) {
    return render(
        <MemoryRouter>
            <ModelWarningBanner {...props} />
        </MemoryRouter>
    );
}
describe("ModelWarningBanner", () => {
    
    test("renders nothing when showWarning is false", () => {
        const { container } = renderBanner({ showWarning: false, hasModelConfigWrite: true });
        expect(container.innerHTML).toBe("");
    });
    test("renders warning text when showWarning is true", () => {
        renderBanner({ showWarning: true, hasModelConfigWrite: false });
        expect(screen.getByText(/No model has been set up/)).toBeInTheDocument();
    });
    test("shows Go to Models button when hasModelConfigWrite is true", () => {
        renderBanner({ showWarning: true, hasModelConfigWrite: true });
        expect(screen.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
        expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
    });
    test("shows admin contact text when hasModelConfigWrite is false", () => {
        renderBanner({ showWarning: true, hasModelConfigWrite: false });
        expect(screen.getByText(/Ask your administrator/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
    });
});
