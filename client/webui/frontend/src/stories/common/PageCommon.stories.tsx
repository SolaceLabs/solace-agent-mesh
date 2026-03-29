import { PageLabel, PageLabelWithValue, PageSection, PageContentWrapper, Metadata, FormFieldLayoutItem } from "@/lib/components/common";
import { Input } from "@/lib/components/ui";
import { expect, screen, within } from "storybook/test";
import type { Meta } from "@storybook/react-vite";

const meta = {
    title: "Common/PageCommon",
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Layout primitives for building consistent page structures. These are pure styling/layout components - pair them with FormComponents for forms.",
            },
        },
    },
} satisfies Meta;

export default meta;

export const PageLabelBasic = {
    render: () => (
        <div className="space-y-6 p-8">
            <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-600">Optional Label</h3>
                <PageLabel>Username</PageLabel>
            </div>
            <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-600">Required Label (with asterisk)</h3>
                <PageLabel required>Password</PageLabel>
            </div>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Username")).toBeInTheDocument();
        const requiredLabel = screen.getByText("Password");
        const labelContainer = requiredLabel.closest("div");
        const asterisk = within(labelContainer!).getByText("*");
        await expect(asterisk).toBeInTheDocument();
    },
};

export const PageLabelWithValueLayout = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">PageLabelWithValue - Grid layout for label + content pairs</h3>
            <PageLabelWithValue className="border border-dashed border-gray-300 p-4">
                <PageLabel>Label goes here</PageLabel>
                <div className="rounded border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600">Form control goes here</div>
            </PageLabelWithValue>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Label goes here")).toBeInTheDocument();
        await expect(screen.getByText("Form control goes here")).toBeInTheDocument();
    },
};

export const PageSectionGrouping = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">PageSection - Vertical spacing for grouped items</h3>
            <PageSection className="space-y-2 border border-dashed border-gray-300 p-4">
                <PageLabel>Section Title</PageLabel>
                <div className="text-sm text-gray-600">Item 1</div>
                <div className="text-sm text-gray-600">Item 2</div>
                <div className="text-sm text-gray-600">Item 3</div>
            </PageSection>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Section Title")).toBeInTheDocument();
        await expect(screen.getByText("Item 1")).toBeInTheDocument();
        await expect(screen.getByText("Item 2")).toBeInTheDocument();
        await expect(screen.getByText("Item 3")).toBeInTheDocument();
    },
};

export const PageContentWrapperLayout = {
    render: () => (
        <div className="flex h-screen flex-col bg-gray-100">
            <div className="border-b border-gray-300 bg-white px-8 py-4">
                <h2 className="text-lg font-bold">Page Header</h2>
                <p className="text-sm text-gray-600">PageContentWrapper is for scrollable content areas</p>
            </div>
            <PageContentWrapper className="bg-white">
                <PageSection>
                    <PageLabel>Section 1</PageLabel>
                    <div className="text-sm text-gray-600">Content for section 1</div>
                </PageSection>
                <PageSection>
                    <PageLabel>Section 2</PageLabel>
                    <div className="text-sm text-gray-600">Content for section 2</div>
                </PageSection>
                <PageSection>
                    <PageLabel>Section 3</PageLabel>
                    <div className="text-sm text-gray-600">Content for section 3</div>
                </PageSection>
            </PageContentWrapper>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Page Header")).toBeInTheDocument();
        await expect(screen.getByText("Section 1")).toBeInTheDocument();
        await expect(screen.getByText("Section 2")).toBeInTheDocument();
        await expect(screen.getByText("Section 3")).toBeInTheDocument();
    },
};

export const MetadataDisplay = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">Metadata - Display read-only key-value pairs in a structured format</h3>
            <Metadata
                metadata={{
                    "Created At": "2024-03-19T10:30:00Z",
                    "Last Updated": "2024-03-19T14:45:00Z",
                    Version: "1.0.0",
                    Status: "Active",
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
        await expect(screen.getByText(/Status:/)).toBeInTheDocument();
    },
};

export const FormFieldLayoutItemBasic = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">FormFieldLayoutItem - Form field wrapper with label and validation</h3>
            <div className="max-w-md">
                <FormFieldLayoutItem label="Username" required>
                    <Input type="text" placeholder="Enter username" />
                </FormFieldLayoutItem>
            </div>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Username")).toBeInTheDocument();
        await expect(screen.getByPlaceholderText("Enter username")).toBeInTheDocument();
    },
};

export const FormFieldLayoutItemWithError = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">With Error State</h3>
            <div className="max-w-md">
                <FormFieldLayoutItem label="Email" required error={{ message: "Invalid email format" }}>
                    <Input type="email" placeholder="Enter email" />
                </FormFieldLayoutItem>
            </div>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Email")).toBeInTheDocument();
        await expect(screen.getByText("Invalid email format")).toBeInTheDocument();
    },
};

export const FormFieldLayoutItemWithHelpText = {
    render: () => (
        <div className="p-8">
            <h3 className="mb-4 text-sm font-semibold text-gray-600">With Help Text</h3>
            <div className="max-w-md">
                <FormFieldLayoutItem label="Password" required helpText="Must be at least 8 characters">
                    <Input type="password" placeholder="Enter password" />
                </FormFieldLayoutItem>
            </div>
        </div>
    ),
    play: async () => {
        await expect(screen.getByText("Password")).toBeInTheDocument();
        await expect(screen.getByText("Must be at least 8 characters")).toBeInTheDocument();
    },
};
