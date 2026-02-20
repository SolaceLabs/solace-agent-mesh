import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within, userEvent } from "storybook/test";
import { DocumentSourcesPanel } from "@/lib/components/chat/rag/DocumentSourcesPanel";
import { documentSearchRagData, singleDocumentSinglePage, documentWithNoPageMetadata, multipleDocumentsOverlappingPages } from "../mocks/citations";

const meta = {
    title: "Chat/DocumentSourcesPanel",
    component: DocumentSourcesPanel,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Document Sources Panel component for displaying document citations grouped by filename and page. Displays in the side panel when document_search results are present.",
            },
        },
    },
    decorators: [
        Story => (
            <div style={{ height: "600px", width: "400px", border: "1px solid #ccc" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof DocumentSourcesPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        ragData: documentSearchRagData,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check header is present
        const header = await canvas.findByText(/3 Documents/);
        expect(header).toBeInTheDocument();
        expect(header).toHaveTextContent("6 Citations");

        // Check accordion items are present
        expect(await canvas.findByText("Source 1")).toBeInTheDocument();
        expect(await canvas.findByText("Source 2")).toBeInTheDocument();
        expect(await canvas.findByText("Source 3")).toBeInTheDocument();
    },
};

export const SingleDocument: Story = {
    args: {
        ragData: singleDocumentSinglePage,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        const header = await canvas.findByText(/1 Document/);
        expect(header).toBeInTheDocument();
        expect(header).toHaveTextContent("1 Citation");

        expect(await canvas.findByText("Source 1")).toBeInTheDocument();
    },
};

export const NoPageMetadata: Story = {
    args: {
        ragData: documentWithNoPageMetadata,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Should show "Unknown page" for sources without page metadata
        const header = await canvas.findByText(/1 Document/);
        expect(header).toBeInTheDocument();
    },
};

export const OverlappingPages: Story = {
    args: {
        ragData: multipleDocumentsOverlappingPages,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        const header = await canvas.findByText(/2 Documents/);
        expect(header).toBeInTheDocument();
        expect(header).toHaveTextContent("4 Citations");
    },
};

export const ExpandedAccordion: Story = {
    args: {
        ragData: documentSearchRagData,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Find and click the first accordion trigger
        const firstSource = await canvas.findByText("Source 1");
        await userEvent.click(firstSource);

        // Check that page citations are visible
        const pageCitations = await canvas.findAllByText(/Page \d+/);
        expect(pageCitations.length).toBeGreaterThan(0);
    },
};

export const Disabled: Story = {
    args: {
        ragData: documentSearchRagData,
        enabled: false,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check disabled state message
        expect(await canvas.findByText("Document Sources")).toBeInTheDocument();
        expect(await canvas.findByText("Source visibility is disabled in settings")).toBeInTheDocument();
    },
};

export const EmptyState: Story = {
    args: {
        ragData: [],
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check empty state message
        expect(await canvas.findByText("Document Sources")).toBeInTheDocument();
        expect(await canvas.findByText("No document sources available yet")).toBeInTheDocument();
    },
};

export const NullData: Story = {
    args: {
        ragData: null,
        enabled: true,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check empty state message
        expect(await canvas.findByText("Document Sources")).toBeInTheDocument();
        expect(await canvas.findByText("No document sources available yet")).toBeInTheDocument();
    },
};
