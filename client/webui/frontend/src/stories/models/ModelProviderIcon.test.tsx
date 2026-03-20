/// <reference types="@testing-library/jest-dom" />
import { render } from "@testing-library/react";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { ModelProviderIcon } from "../../lib/components/models/ModelProviderIcon";

expect.extend(matchers);

describe("ModelProviderIcon", () => {
    test("renders provider icon for known provider", () => {
        const { container } = render(<ModelProviderIcon provider="openai" />);
        const img = container.querySelector("img");
        expect(img).toBeInTheDocument();
        expect(img).toHaveAttribute("alt", "openai");
    });

    test("renders fallback initials for unknown provider", () => {
        const { container } = render(<ModelProviderIcon provider="unknown_provider" />);
        const span = container.querySelector("span");
        expect(span).toHaveTextContent("U");
    });

    test("applies correct size classes", () => {
        const { container: containerSm } = render(<ModelProviderIcon provider="openai" size="sm" />);
        expect(containerSm.querySelector("div")).toHaveClass("h-8", "w-8");

        const { container: containerMd } = render(<ModelProviderIcon provider="openai" size="md" />);
        expect(containerMd.querySelector("div")).toHaveClass("h-12", "w-12");
    });
});
