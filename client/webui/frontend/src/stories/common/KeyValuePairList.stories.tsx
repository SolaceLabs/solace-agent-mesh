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
