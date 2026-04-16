/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

const mockModelConfigStatus = vi.fn<() => { data: { configured: boolean } | undefined }>();
vi.mock("@/lib/api/models", () => ({
    useModelConfigStatus: () => mockModelConfigStatus(),
}));

const { ModelWarningBanner } = await import("@/lib/components/models/ModelWarningBanner");

function renderBanner({ configured, modelConfigUiEnabled, hasModelConfigWrite }: { configured: boolean | undefined; modelConfigUiEnabled: boolean; hasModelConfigWrite: boolean }) {
    mockModelConfigStatus.mockReturnValue({ data: configured === undefined ? undefined : { configured } });
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={{ hasModelConfigWrite }} configContextValues={{ configFeatureEnablement: { model_config_ui: modelConfigUiEnabled } }}>
                <ModelWarningBanner />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("ModelWarningBanner", () => {
    test("renders nothing when model_config_ui flag is disabled", async () => {
        renderBanner({ configured: false, modelConfigUiEnabled: false, hasModelConfigWrite: true });
        await new Promise(r => setTimeout(r, 0));
        expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
    });

    test("renders nothing when models are already configured", async () => {
        renderBanner({ configured: true, modelConfigUiEnabled: true, hasModelConfigWrite: true });
        await new Promise(r => setTimeout(r, 0));
        expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
    });

    test("renders warning text when models not configured and flag enabled", async () => {
        renderBanner({ configured: false, modelConfigUiEnabled: true, hasModelConfigWrite: false });
        expect(await screen.findByText(/Default models have not been configured/)).toBeInTheDocument();
    });

    test("shows Go to Models button when hasModelConfigWrite is true", async () => {
        renderBanner({ configured: false, modelConfigUiEnabled: true, hasModelConfigWrite: true });
        expect(await screen.findByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
        expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
    });

    test("shows admin contact text when hasModelConfigWrite is false", async () => {
        renderBanner({ configured: false, modelConfigUiEnabled: true, hasModelConfigWrite: false });
        expect(await screen.findByText(/Ask your administrator/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
    });
});
