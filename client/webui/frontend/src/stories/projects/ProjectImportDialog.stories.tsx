import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";
import { ProjectImportDialog } from "@/lib";
import JSZip from "jszip";

// ============================================================================
// Mock ZIP File Helpers
// ============================================================================

interface ProjectData {
    name: string;
    description?: string;
    systemPrompt?: string;
    defaultAgentId?: string;
    artifactCount?: number;
}

/**
 * Creates a valid mock project ZIP file for testing
 */
async function createValidProjectZip(projectData: ProjectData): Promise<File> {
    const zip = new JSZip();

    const projectJson = {
        version: "1.0",
        project: {
            name: projectData.name,
            description: projectData.description || "",
            systemPrompt: projectData.systemPrompt || null,
            defaultAgentId: projectData.defaultAgentId || null,
        },
        artifacts: [] as Array<{ filename: string; size: number; mime_type: string }>,
    };

    if (projectData.artifactCount && projectData.artifactCount > 0) {
        for (let i = 0; i < projectData.artifactCount; i++) {
            const filename = `artifact-${i + 1}.txt`;
            const content = `This is artifact ${i + 1} content`;
            zip.file(`artifacts/${filename}`, content);

            projectJson.artifacts.push({
                filename,
                size: content.length,
                mime_type: "text/plain",
            });
        }
    }

    zip.file("project.json", JSON.stringify(projectJson, null, 2));
    const blob = await zip.generateAsync({ type: "blob" });
    return new File([blob], `${projectData.name.replace(/\s+/g, "-")}.zip`, { type: "application/zip" });
}

/**
 * Creates an invalid ZIP file (not a project export)
 */
async function createInvalidZip(): Promise<File> {
    const zip = new JSZip();
    zip.file("random-file.txt", "This is not a project export");
    const blob = await zip.generateAsync({ type: "blob" });
    return new File([blob], "invalid.zip", { type: "application/zip" });
}

/**
 * Creates a non-ZIP file
 */
function createNonZipFile(): File {
    const content = "This is a text file, not a ZIP";
    const blob = new Blob([content], { type: "text/plain" });
    return new File([blob], "not-a-zip.txt", { type: "text/plain" });
}

// ============================================================================
// Story Configuration
// ============================================================================

const meta = {
    title: "Pages/Projects/ProjectImportDialog",
    component: ProjectImportDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for importing a project from an exported ZIP file. Validates the file, shows a preview, and allows customizing the project name.",
            },
        },
    },
} satisfies Meta<typeof ProjectImportDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

// ============================================================================
// Stories
// ============================================================================

/**
 * Default state with empty file upload
 */
export const Default: Story = {
    args: {
        open: true,
        onOpenChange: () => alert("Dialog will close."),
        onImport: async () => {},
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByRole("button", { name: "Upload File" })).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Import" })).toBeDisabled();
    },
};

/**
 * Invalid ZIP file - shows error when file is missing project.json
 */
export const InvalidProjectZip: Story = {
    args: {
        open: true,
        onOpenChange: () => console.log("Dialog closed"),
        onImport: async () => {},
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const invalidFile = await createInvalidZip();
        const fileInput = (await dialogContent.findByTestId("projectImportFileInput")) as HTMLInputElement;
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(invalidFile);
        fileInput.files = dataTransfer.files;
        fileInput.dispatchEvent(new Event("change", { bubbles: true }));

        expect(await dialogContent.findByText(/Invalid project export/i)).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Import" })).toBeDisabled();
    },
};

/**
 * Non-ZIP file - shows error when selecting wrong file type
 */
export const NonZipFile: Story = {
    args: {
        open: true,
        onOpenChange: () => console.log("Dialog closed"),
        onImport: async () => {},
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const textFile = createNonZipFile();
        const fileInput = (await dialogContent.findByTestId("projectImportFileInput")) as HTMLInputElement;
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(textFile);
        fileInput.files = dataTransfer.files;
        fileInput.dispatchEvent(new Event("change", { bubbles: true }));

        expect(await dialogContent.findByText("Please select a ZIP file")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Import" })).toBeDisabled();
    },
};

/**
 * Valid project with artifacts - shows preview with all project details
 */
export const ValidProjectWithArtifacts: Story = {
    args: {
        open: true,
        onOpenChange: () => console.log("Dialog closed"),
        onImport: async (file, options) => {
            console.log("Importing project:", file.name, options);
        },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const validFile = await createValidProjectZip({
            name: "E-commerce Platform",
            description: "Online shopping platform with user authentication and payment processing",
            systemPrompt: "You are a helpful assistant for e-commerce development tasks.",
            defaultAgentId: "OrchestratorAgent",
            artifactCount: 6,
        });

        const fileInput = (await dialogContent.findByTestId("projectImportFileInput")) as HTMLInputElement;
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(validFile);
        fileInput.files = dataTransfer.files;
        fileInput.dispatchEvent(new Event("change", { bubbles: true }));

        expect(await dialogContent.findByText("Artifacts (6 files)")).toBeInTheDocument();
        expect(await dialogContent.findByText("artifact-1.txt")).toBeInTheDocument();
        expect(await dialogContent.findByText("+ 1 more files")).toBeInTheDocument();

        const nameInput = (await dialogContent.findByLabelText("Project Name")) as HTMLInputElement;
        expect(nameInput.value).toBe("E-commerce Platform");

        expect(await dialogContent.findByRole("button", { name: "Import" })).toBeEnabled();
    },
};
