import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { Citation, BundledCitations } from "@/lib/components/chat/Citation";
import { documentCitation, webSearchCitation, researchCitation, multipleDocumentCitations, multipleWebCitations, multipleResearchCitations } from "../mocks/citations";

const meta = {
    title: "Chat/Citation",
    component: Citation,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Citation badge component for displaying clickable source citations. Supports document, web search, and deep research citation types. Also includes BundledCitations for grouped citations.",
            },
        },
    },
    argTypes: {
        onClick: { action: "clicked" },
    },
} satisfies Meta<typeof Citation>;

export default meta;
type CitationStory = StoryObj<typeof meta>;

export const DocumentCitation: CitationStory = {
    args: {
        citation: documentCitation,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("quarterly_report.pdf");
        expect(badge).toHaveTextContent("Pages 3-5");
        expect(badge.querySelector(".lucide-external-link")).toBeNull();
    },
};

export const WebSearchCitation: CitationStory = {
    args: {
        citation: webSearchCitation,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("example.com");
        expect(badge.querySelector(".lucide-external-link")).toBeInTheDocument();
    },
};

export const ResearchCitation: CitationStory = {
    args: {
        citation: researchCitation,
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("research.university.edu");
        expect(badge.querySelector(".lucide-external-link")).toBeInTheDocument();
    },
};

export const CitationWithoutSource: CitationStory = {
    args: {
        citation: {
            marker: "[[cite:idx0r0]]",
            type: "document",
            sourceId: 0,
            position: 0,
            citationId: "idx0r0",
            source: undefined,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("Source 1");
    },
};

export const SingleBundledCitation = {
    render: () => <BundledCitations citations={[documentCitation]} />,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("quarterly_report.pdf");
        expect(badge.textContent).not.toMatch(/\+\d+/);
    },
};

export const BundledDocumentCitations = {
    render: () => <BundledCitations citations={multipleDocumentCitations} />,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("quarterly_report.pdf");
        expect(badge).toHaveTextContent("+2");
        expect(badge.querySelector(".lucide-external-link")).toBeNull();
    },
};

export const BundledWebCitations = {
    render: () => <BundledCitations citations={multipleWebCitations} />,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("example.com");
        expect(badge).toHaveTextContent("+2");
        expect(badge.querySelector(".lucide-external-link")).toBeInTheDocument();
    },
};

export const BundledResearchCitations = {
    render: () => <BundledCitations citations={multipleResearchCitations} />,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveTextContent("research.university.edu");
        expect(badge).toHaveTextContent("+1");
    },
};

export const BundledWebCitationsWithPopover = {
    render: () => <BundledCitations citations={multipleWebCitations} />,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const badge = await canvas.findByRole("button");

        await userEvent.hover(badge);

        const popoverHeader = await screen.findByText(/All Sources/);
        expect(popoverHeader).toBeInTheDocument();

        const exampleLinks = await screen.findAllByText("example.com");
        expect(exampleLinks.length).toBeGreaterThanOrEqual(2);
        expect(await screen.findByText("techblog.io")).toBeInTheDocument();
        expect(await screen.findByText("news.site")).toBeInTheDocument();
    },
};
