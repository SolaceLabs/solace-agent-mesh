import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
import { EditFileDescriptionDialog } from "@/lib";
import type { ArtifactInfo } from "@/lib/types";

// ============================================================================
// Mock Data
// ============================================================================

const mockArtifact: ArtifactInfo = {
    filename: "api-documentation.pdf",
    mime_type: "application/pdf",
    size: 524288,
    last_modified: new Date("2024-03-15T10:00:00Z").toISOString(),
    description: "API reference documentation",
};

const mockArtifactNoDescription: ArtifactInfo = {
    filename: "package.json",
    mime_type: "application/json",
    size: 1024,
    last_modified: new Date("2024-03-17T09:45:00Z").toISOString(),
    description: "",
};

// ============================================================================
// Story Configuration
// ============================================================================

const meta = {
    title: "Pages/Projects/EditFileDescriptionDialog",
    component: EditFileDescriptionDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for editing the description of an uploaded project file.",
            },
        },
    },
} satisfies Meta<typeof EditFileDescriptionDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

// ============================================================================
// Stories
// ============================================================================

/**
 * Default state with existing description
 */
export const Default: Story = {
    args: {
        isOpen: true,
        artifact: mockArtifact,
        onClose: () => alert("Dialog will close."),
        onSave: async () => {},
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);
        expect(await dialogContent.findByText("api-documentation.pdf")).toBeVisible();
        expect(await dialogContent.findByText("API reference documentation")).toBeVisible();
        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeVisible();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeVisible();
    },
};

/**
 * Empty state - no existing description
 */
export const Empty: Story = {
    args: {
        isOpen: true,
        artifact: mockArtifactNoDescription,
        onClose: () => alert("Dialog will close."),
        onSave: async () => {},
        isSaving: false,
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("package.json")).toBeVisible();

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeEnabled();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeEnabled();
        
    },
};
