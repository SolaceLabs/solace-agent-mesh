/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

const mockModelConfigStatus = vi.fn<() => { data: { configured: boolean } | undefined }>();
vi.mock("@/lib/api/models", () => ({
    useModelConfigStatus: () => mockModelConfigStatus(),
}));

const { ModelWarningBanner } = await import("@/lib/components/models/ModelWarningBanner");

function renderBanner(chatContextValues = {}, featureFlags: Record<string, boolean> = { model_config_ui: true }) {
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={chatContextValues} configContextValues={{ configFeatureEnablement: featureFlags }}>
                <ModelWarningBanner />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("ModelWarningBanner", () => {
    beforeEach(() => mockModelConfigStatus.mockReset());

    test("renders nothing when models are configured", () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: true } });
        renderBanner();
        expect(screen.queryByText(/No model has been set up/)).not.toBeInTheDocument();
    });

    test("renders warning text when models not configured", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner();
        await waitFor(() => {
            expect(screen.getByText(/No model has been set up/)).toBeInTheDocument();
        });
    });

    test("shows Go to Models button when hasModelConfigWrite is true", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner({ hasModelConfigWrite: true });
        await waitFor(() => {
            expect(screen.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
        });
        expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
    });

    test("shows admin contact text when hasModelConfigWrite is false", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner({ hasModelConfigWrite: false });
        await waitFor(() => {
            expect(screen.getByText(/Ask your administrator/)).toBeInTheDocument();
        });
        expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
    });
});
