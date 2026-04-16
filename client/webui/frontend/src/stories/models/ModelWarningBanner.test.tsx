/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

expect.extend(matchers);

const mockUseModelConfigStatus = vi.fn();
const mockUseBooleanFlagDetails = vi.fn();
const mockUseChatContext = vi.fn();

describe("ModelWarningBanner", () => {
    let ModelWarningBanner: React.ComponentType;

    beforeEach(async () => {
        vi.resetModules();
        mockUseModelConfigStatus.mockReset();
        mockUseBooleanFlagDetails.mockReset();
        mockUseChatContext.mockReset();

        mockUseBooleanFlagDetails.mockReturnValue({ value: true });
        mockUseChatContext.mockReturnValue({ hasModelConfigWrite: false });

        vi.doMock("@/lib/api/models", () => ({
            useModelConfigStatus: mockUseModelConfigStatus,
        }));

        vi.doMock("@openfeature/react-sdk", async () => {
            const actual = await vi.importActual<typeof import("@openfeature/react-sdk")>("@openfeature/react-sdk");
            return {
                ...actual,
                useBooleanFlagDetails: mockUseBooleanFlagDetails,
            };
        });

        vi.doMock("@/lib/hooks", async () => {
            const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
            return {
                ...actual,
                useChatContext: mockUseChatContext,
            };
        });

        const mod = await import("@/lib/components/models/ModelWarningBanner");
        ModelWarningBanner = mod.ModelWarningBanner;
    });

    function renderBanner() {
        return render(
            <MemoryRouter>
                <ModelWarningBanner />
            </MemoryRouter>
        );
    }

    test("renders nothing when models are configured", () => {
        mockUseModelConfigStatus.mockReturnValue({ data: { configured: true } });
        renderBanner();
        expect(screen.queryByText(/Default models have not been configured./)).not.toBeInTheDocument();
    });

    test("renders warning text when models not configured", () => {
        mockUseModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner();
        expect(screen.getByText(/Default models have not been configured./)).toBeInTheDocument();
    });

    test("shows Go to Models button when hasModelConfigWrite is true", () => {
        mockUseChatContext.mockReturnValue({ hasModelConfigWrite: true });
        mockUseModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner();
        expect(screen.getByRole("button", { name: /Go to Models/i })).toBeInTheDocument();
        expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
    });

    test("shows admin contact text when hasModelConfigWrite is false", () => {
        mockUseChatContext.mockReturnValue({ hasModelConfigWrite: false });
        mockUseModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner();
        expect(screen.getByText(/Ask your administrator/)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
    });

    test("renders nothing when model_config_ui flag is disabled", () => {
        mockUseBooleanFlagDetails.mockReturnValue({ value: false });
        mockUseModelConfigStatus.mockReturnValue({ data: { configured: false } });
        renderBanner();
        expect(screen.queryByText(/Default models have not been configured./)).not.toBeInTheDocument();
    });
});
