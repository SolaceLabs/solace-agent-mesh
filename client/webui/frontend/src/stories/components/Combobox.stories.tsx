import { useState } from "react";
import { ComboBox } from "@/lib/components/ui";
import { comboBoxMockData } from "@/stories/data/combobox";
import { expect, userEvent, within, screen, fn } from "storybook/test";
import type { Meta, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Components/ComboBox",
    component: ComboBox,
    parameters: {
        layout: "padded",
        docs: {
            description: {
                component: "A customizable combobox component with search, keyboard navigation, and grouped items support.",
            },
        },
    },
} satisfies Meta<typeof ComboBox>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Basic: Story = {
    args: {
        items: comboBoxMockData.basicItems,
        placeholder: "Select an option...",
        onValueChange: fn(),
        onOpen: fn(),
    },
    render: args => {
        const [selected, setSelected] = useState<string | undefined>();

        return (
            <div className="max-w-sm">
                <ComboBox
                    {...args}
                    value={selected}
                    onValueChange={value => {
                        setSelected(value);
                        args.onValueChange(value);
                    }}
                />
            </div>
        );
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByPlaceholderText("Select an option...");

        // Click to open dropdown
        await userEvent.click(input);

        // Check that items appear
        await expect(await screen.findByText("First Option")).toBeInTheDocument();
        await expect(await screen.findByText("Second Option")).toBeInTheDocument();
        await expect(await screen.findByText("Third Option")).toBeInTheDocument();
    },
};

export const DefaultSelection: Story = {
    args: {
        value: "option-2",
        items: comboBoxMockData.basicItems,
        placeholder: "Select an option...",
        onValueChange: () => {},
    },
    render: args => {
        const [selected, setSelected] = useState<string | undefined>(args.value);

        return (
            <div className="max-w-sm">
                <ComboBox {...args} value={selected} onValueChange={setSelected} />
            </div>
        );
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByDisplayValue("Second Option");

        // Check selected value is displayed
        await expect(input).toBeInTheDocument();
    },
};

export const WithSubtext: Story = {
    args: {
        items: comboBoxMockData.itemsWithSubtext,
        placeholder: "Select a language...",
        onValueChange: () => {},
    },
    render: args => {
        const [selected, setSelected] = useState<string | undefined>();

        return (
            <div className="max-w-sm">
                <ComboBox {...args} value={selected} onValueChange={setSelected} />
            </div>
        );
    },
};

export const WithSections: Story = {
    args: {
        items: comboBoxMockData.itemsWithSections,
        placeholder: "Select a model...",
        onValueChange: fn(),
        onOpen: fn(),
    },
    render: args => {
        const [selected, setSelected] = useState<string | undefined>();

        return (
            <div className="max-w-sm">
                <ComboBox
                    {...args}
                    value={selected}
                    onValueChange={value => {
                        setSelected(value);
                        args.onValueChange(value);
                    }}
                />
            </div>
        );
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByPlaceholderText("Select a model...");

        // Click to open dropdown
        await userEvent.click(input);

        // Check default section items
        await expect(await screen.findByText("Common Model")).toBeInTheDocument();
        await expect(await screen.findByText("General Purpose")).toBeInTheDocument();

        // Check advanced section items
        await expect(await screen.findByText("Specialized Model")).toBeInTheDocument();
        await expect(await screen.findByText("Research Model")).toBeInTheDocument();
    },
};

export const Loading: Story = {
    args: {
        items: [],
        placeholder: "Loading options...",
        isLoading: true,
        onValueChange: fn(),
    },
    render: args => (
        <div className="max-w-sm">
            <ComboBox {...args} />
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByPlaceholderText("Loading options...");

        // Check input is disabled during loading
        await expect(input).toBeDisabled();

        // Check spinner appears
        const spinner = canvasElement.querySelector('[class*="animate-spin"]');
        await expect(spinner).toBeInTheDocument();
    },
};

export const Disabled: Story = {
    args: {
        value: "option-2",
        items: comboBoxMockData.basicItems,
        placeholder: "Select an option...",
        disabled: true,
        onValueChange: fn(),
    },
    render: args => (
        <div className="max-w-sm">
            <ComboBox {...args} />
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByDisplayValue("Second Option");

        // Check input is disabled
        await expect(input).toBeDisabled();
    },
};

export const WithCustomRendering: Story = {
    args: {
        items: comboBoxMockData.itemsWithImages,
        placeholder: "Select a provider...",
        onValueChange: fn(),
    },
    render: args => {
        const [selected, setSelected] = useState<string | undefined>();

        return (
            <div className="max-w-sm">
                <ComboBox
                    {...args}
                    value={selected}
                    onValueChange={setSelected}
                    renderItem={item => (
                        <div className="flex items-center gap-3">
                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-blue-600 text-xs font-bold text-white">{item.label[0]}</div>
                            <div>
                                <div className="font-medium">{item.label}</div>
                                {item.subtext && <div className="text-xs text-gray-500">{item.subtext}</div>}
                            </div>
                        </div>
                    )}
                />
            </div>
        );
    },
};
