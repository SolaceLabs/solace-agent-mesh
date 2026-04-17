/// <reference types="@testing-library/jest-dom" />
import { screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { renderWithProviders } from "@/lib/test-utils";
import * as modelsApi from "@/lib/api/models";
import { ModelWarningBanner } from "@/lib/components/models/ModelWarningBanner";

expect.extend(matchers);

const mockModelConfigStatus = vi.fn<() => { data: { configured: boolean } | undefined }>();

beforeEach(() => {
    vi.spyOn(modelsApi, "useModelConfigStatus").mockImplementation((() => mockModelConfigStatus()) as unknown as typeof modelsApi.useModelConfigStatus);
});

describe("ModelWarningBanner", () => {
    test("renders nothing when model_config_ui flag is disabled", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        await renderWithProviders(<ModelWarningBanner />, {
            featureFlags: { model_config_ui: false },
            chatContextValues: { hasModelConfigWrite: true },
        });
        expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
    });

    test("renders nothing when models are already configured", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: true } });
        await renderWithProviders(<ModelWarningBanner />, {
            featureFlags: { model_config_ui: true },
            chatContextValues: { hasModelConfigWrite: true },
        });
        expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
    });

    test("renders warning text when models not configured and flag enabled", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        await renderWithProviders(<ModelWarningBanner />, {
            featureFlags: { model_config_ui: true },
            chatContextValues: { hasModelConfigWrite: false },
        });
        expect(screen.getByText(/Default models have not been configured/)).toBeInTheDocument();
    });

    test("shows Go to Models button when hasModelConfigWrite is true", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        await renderWithProviders(<ModelWarningBanner />, {
            featureFlags: { model_config_ui: true },
            chatContextValues: { hasModelConfigWrite: true },
        });
        expect(screen.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
        expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
    });

    test("shows admin contact text when hasModelConfigWrite is false", async () => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        await renderWithProviders(<ModelWarningBanner />, {
            featureFlags: { model_config_ui: true },
            chatContextValues: { hasModelConfigWrite: false },
        });
        expect(screen.getByText(/Ask your administrator/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
    });
});
