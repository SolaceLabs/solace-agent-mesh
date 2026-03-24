import { useForm, FormProvider } from "react-hook-form";
import { KeyValuePairList } from "@/lib/components/common/KeyValuePairList";
import { expect, within } from "storybook/test";
import type { Meta, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/KeyValuePairList",
    component: KeyValuePairList,
    parameters: {
        layout: "padded",
        docs: {
            description: {
                component: "A reusable component for managing key-value pair inputs in forms using react-hook-form.",
            },
        },
    },
    decorators: [
        Story => {
            const form = useForm({
                defaultValues: {
                    pairs: [{ key: "", value: "" }],
                },
            });

            return (
                <FormProvider {...form}>
                    <form>
                        <Story />
                    </form>
                </FormProvider>
            );
        },
    ],
} satisfies Meta<typeof KeyValuePairList>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Basic: Story = {
    args: {
        name: "pairs",
        minPairs: 1,
    },
    render: args => (
        <div className="max-w-md">
            <div className="mb-2 space-y-2">
                <h3 className="text-sm font-semibold">Key-Value Pair List</h3>
            </div>
            <KeyValuePairList {...args} />
        </div>
    ),
    play: async ({ canvasElement }) => {
        // Check that key and value inputs are rendered
        const keyInputs = canvasElement.querySelectorAll('input[type="text"]');
        expect(keyInputs.length).toBeGreaterThanOrEqual(2);
    },
};

export const MultipleMinPairs: Story = {
    args: { name: "headers", minPairs: 2 },
    render: () => {
        const form = useForm({
            defaultValues: {
                headers: [
                    { key: "Content-Type", value: "application/json" },
                    { key: "Authorization", value: "Bearer token" },
                    { key: "", value: "" },
                ],
            },
        });

        return (
            <FormProvider {...form}>
                <form className="max-w-md">
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium">HTTP Headers</h3>
                        <KeyValuePairList name="headers" minPairs={2} />
                    </div>
                </form>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check title appears
        await expect(await canvas.findByText("HTTP Headers")).toBeInTheDocument();

        // Check inputs are rendered
        const inputs = canvasElement.querySelectorAll('input[type="text"]');
        expect(inputs.length).toBeGreaterThanOrEqual(4);
    },
};

export const WithError: Story = {
    args: { name: "pairs", minPairs: 1, error: { root: { message: "At least one key-value pair is required" } } },
    render: () => {
        const form = useForm({
            defaultValues: {
                pairs: [{ key: "", value: "" }],
            },
        });

        return (
            <FormProvider {...form}>
                <form className="max-w-md">
                    <KeyValuePairList name="pairs" minPairs={1} error={{ root: { message: "At least one key-value pair is required" } }} />
                </form>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check error message appears
        await expect(await canvas.findByText("At least one key-value pair is required")).toBeInTheDocument();
    },
};

export const RemoveButtonBehavior: Story = {
    args: { name: "pairs", minPairs: 1 },
    render: () => {
        const form = useForm({
            defaultValues: {
                pairs: [
                    { key: "key1", value: "value1" },
                    { key: "key2", value: "value2" },
                    { key: "key3", value: "value3" },
                ],
            },
        });

        return (
            <FormProvider {...form}>
                <form className="max-w-md">
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium">Remove pairs (only last pair can be removed)</h3>
                        <KeyValuePairList name="pairs" minPairs={1} />
                    </div>
                </form>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }) => {
        // Should have 3 remove buttons (more than minPairs of 1)
        const removeButtons = canvasElement.querySelectorAll('[title="Remove pair"]');
        await expect(removeButtons.length).toBe(3);

        // Verify all inputs are present
        const inputs = canvasElement.querySelectorAll('input[type="text"]');
        await expect(inputs.length).toBe(6); // 2 inputs per pair * 3 pairs
    },
};

export const MinPairsEnforcement: Story = {
    args: { name: "headers", minPairs: 3 },
    render: () => {
        const form = useForm({
            defaultValues: {
                headers: [
                    { key: "Authorization", value: "Bearer token" },
                    { key: "Content-Type", value: "application/json" },
                    { key: "Accept", value: "application/json" },
                    { key: "User-Agent", value: "MyApp/1.0" },
                ],
            },
        });

        return (
            <FormProvider {...form}>
                <form className="max-w-md">
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium">HTTP Headers (minimum 3 required)</h3>
                        <KeyValuePairList name="headers" minPairs={3} />
                    </div>
                </form>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }) => {
        // With 4 pairs and minPairs=3, only the last pair should have remove button
        const removeButtons = canvasElement.querySelectorAll('[title="Remove pair"]');
        await expect(removeButtons.length).toBe(1);

        // Verify all 4 pairs are rendered
        const inputs = canvasElement.querySelectorAll('input[type="text"]');
        await expect(inputs.length).toBe(8); // 2 inputs * 4 pairs
    },
};

export const KeyValueHeaderLabels: Story = {
    args: { name: "pairs", minPairs: 1 },
    render: () => {
        const form = useForm({
            defaultValues: {
                pairs: [
                    { key: "name", value: "John" },
                    { key: "age", value: "30" },
                ],
            },
        });

        return (
            <FormProvider {...form}>
                <form className="max-w-md">
                    <div className="space-y-2">
                        <h3 className="text-sm font-medium">Key-Value headers display</h3>
                        <KeyValuePairList name="pairs" minPairs={1} />
                    </div>
                </form>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }) => {
        // Check that Key and Value labels exist
        const allText = canvasElement.textContent;
        await expect(allText).toContain("Key");
        await expect(allText).toContain("Value");
    },
};
