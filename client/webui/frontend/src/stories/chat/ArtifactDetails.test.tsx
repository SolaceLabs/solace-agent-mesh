/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ArtifactDetails } from "@/lib/components/chat/artifact/ArtifactDetails";
import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";
import type { ArtifactInfo } from "@/lib/types";

expect.extend(matchers);

const baseArtifact: ArtifactInfo = {
    filename: "report.pdf",
    mime_type: "application/pdf",
    size: 1024,
    last_modified: "2024-01-01T00:00:00.000Z",
    uri: "artifact://report.pdf",
};

function withChatContext(value: Partial<ChatContextValue>, children: React.ReactNode) {
    return <ChatContext.Provider value={value as ChatContextValue}>{children}</ChatContext.Provider>;
}

describe("ArtifactDetails outside a ChatProvider", () => {
    test("renders filename without throwing when no ChatContext is present", () => {
        render(<ArtifactDetails artifactInfo={baseArtifact} isPreview />);
        expect(screen.getByText("report.pdf")).toBeInTheDocument();
    });

    test("hides version selector when no ChatContext is present even with isPreview=true", () => {
        render(<ArtifactDetails artifactInfo={baseArtifact} isPreview />);
        expect(screen.queryByText("Version")).not.toBeInTheDocument();
    });

    test("invokes onDownload when download button is clicked", () => {
        const onDownload = vi.fn();
        render(<ArtifactDetails artifactInfo={baseArtifact} onDownload={onDownload} isPreview />);
        fireEvent.click(screen.getByRole("button", { name: /download/i }));
        expect(onDownload).toHaveBeenCalledWith(baseArtifact);
    });

    test("invokes onDelete when delete button is clicked", () => {
        const onDelete = vi.fn();
        render(<ArtifactDetails artifactInfo={baseArtifact} onDelete={onDelete} isPreview />);
        fireEvent.click(screen.getByRole("button", { name: /delete/i }));
        expect(onDelete).toHaveBeenCalledTimes(1);
    });
});

describe("ArtifactDetails inside a ChatProvider", () => {
    test("hides version selector when only one version is available", () => {
        render(
            withChatContext(
                {
                    previewedArtifactAvailableVersions: [1],
                    currentPreviewedVersionNumber: 1,
                    navigateArtifactVersion: vi.fn(),
                },
                <ArtifactDetails artifactInfo={baseArtifact} isPreview />
            )
        );
        expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    });

    test("renders version selector when multiple versions are available and isPreview=true", () => {
        render(
            withChatContext(
                {
                    previewedArtifactAvailableVersions: [1, 2, 3],
                    currentPreviewedVersionNumber: 2,
                    navigateArtifactVersion: vi.fn(),
                },
                <ArtifactDetails artifactInfo={baseArtifact} isPreview />
            )
        );
        expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    test("hides version selector when isPreview=false even with multiple versions", () => {
        render(
            withChatContext(
                {
                    previewedArtifactAvailableVersions: [1, 2, 3],
                    currentPreviewedVersionNumber: 2,
                    navigateArtifactVersion: vi.fn(),
                },
                <ArtifactDetails artifactInfo={baseArtifact} />
            )
        );
        expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    });
});
