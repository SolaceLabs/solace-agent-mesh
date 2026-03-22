import { PageLabel, PageLabelWithValue, PageSection, PageContentWrapper, Metadata } from "@/lib/components/common";
import { Input } from "@/lib/components/ui/input";
import { expect, screen, within } from "storybook/test";
import type { Meta } from "@storybook/react-vite";

const meta = {
    title: "Common/PageCommon",
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "A collection of layout components for building consistent page structures",
            },
        },
    },
} satisfies Meta;

export default meta;

export const PageLabelExample = {
    render: () => (
        <div className="p-8">
            <h2 className="mb-6 text-lg font-bold">PageLabel - label rendering with optional required indicator</h2>
            <div className="space-y-4">
                <div>
                    <h3 className="mb-2 text-sm font-semibold">Default Label</h3>
                    <PageLabel>Field Label</PageLabel>
                </div>
                <div>
                    <h3 className="mb-2 text-sm font-semibold">Required Label</h3>
                    <PageLabel required>Required Field</PageLabel>
                </div>
            </div>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Field Label")).toBeInTheDocument();
        const requiredLabel = screen.getByText("Required Field");
        const labelContainer = requiredLabel.closest("div");
        const asterisk = within(labelContainer!).queryByText("*");
        await expect(asterisk).toBeInTheDocument();
    },
};

export const PageLabelWithValueExample = {
    render: () => (
        <div className="p-8">
            <h2 className="mb-6 text-lg font-bold">PageLabelWithValue - label paired with a form control</h2>
            <PageLabelWithValue className="custom-test-class">
                <PageLabel required>Select Option</PageLabel>
                <select className="w-full rounded border border-gray-300 p-2">
                    <option>Option 1</option>
                    <option>Option 2</option>
                    <option>Option 3</option>
                </select>
            </PageLabelWithValue>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Select Option")).toBeInTheDocument();
        const selectElement = screen.getByRole("combobox");
        await expect(selectElement).toBeInTheDocument();
        const wrapper = selectElement.parentElement;
        await expect(wrapper).toHaveClass("custom-test-class");
    },
};

export const PageSectionExample = {
    render: () => (
        <div className="p-8">
            <h2 className="mb-6 text-lg font-bold">PageSection - section container for grouped form fields</h2>
            <PageSection className="custom-section-class">
                <PageLabel required>Username</PageLabel>
                <Input placeholder="Enter username" />
            </PageSection>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Username")).toBeInTheDocument();
        const input = screen.getByPlaceholderText("Enter username");
        await expect(input).toBeInTheDocument();
        const section = input.parentElement;
        await expect(section).toHaveClass("custom-section-class");
    },
};

export const PageContentWrapperExample = {
    render: () => (
        <div className="flex h-screen flex-col">
            <div className="border-b border-(--secondary-w20) px-8 py-4">
                <h2 className="text-lg font-bold">PageContentWrapper - scrollable content wrapper with sections</h2>
            </div>
            <PageContentWrapper className="custom-wrapper-class">
                <PageSection>
                    <PageLabel>Field 1</PageLabel>
                    <Input placeholder="Enter value" />
                </PageSection>
                <PageSection>
                    <PageLabel>Field 2</PageLabel>
                    <Input placeholder="Enter value" />
                </PageSection>
            </PageContentWrapper>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Field 1")).toBeInTheDocument();
        await expect(screen.getByText("Field 2")).toBeInTheDocument();
        const inputs = screen.getAllByPlaceholderText("Enter value");
        const wrapper = inputs[0].closest(".custom-wrapper-class");
        await expect(wrapper).toHaveClass("custom-wrapper-class");
    },
};

export const MetadataExample = {
    render: () => (
        <div className="p-8">
            <h2 className="mb-6 text-lg font-bold">Metadata - metadata display with key-value pairs</h2>
            <Metadata
                metadata={{
                    "Created At": "2024-03-19T10:30:00Z",
                    "Last Updated": "2024-03-19T14:45:00Z",
                    Version: "1.0.0",
                }}
            />
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Metadata")).toBeInTheDocument();
        await expect(screen.getByText(/Created At:/)).toBeInTheDocument();
        await expect(screen.getByText(/Last Updated:/)).toBeInTheDocument();
        await expect(screen.getByText(/Version:/)).toBeInTheDocument();
        await expect(screen.getByText("1.0.0")).toBeInTheDocument();
    },
};
