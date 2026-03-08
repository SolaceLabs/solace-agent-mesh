import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";

const meta = {
    title: "Components/Select",
    component: Select,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The select component with various states",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center", padding: "2rem" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof Select>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    render: () => (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem", width: "400px" }}>
            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Default Select</label>
                <Select>
                    <SelectTrigger>
                        <SelectValue placeholder="Select an option..." />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                        <SelectItem value="option3">Option 3</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>With Selected Value</label>
                <Select defaultValue="option2">
                    <SelectTrigger>
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                        <SelectItem value="option3">Option 3</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Disabled Select</label>
                <Select disabled defaultValue="option2">
                    <SelectTrigger>
                        <SelectValue placeholder="Cannot interact" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Readonly Select</label>
                <Select readonly defaultValue="option2">
                    <SelectTrigger readonly>
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                        <SelectItem value="option3">Option 3</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Error State (invalid prop)</label>
                <Select defaultValue="option2">
                    <SelectTrigger invalid={true} className="w-full max-w-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                        <SelectItem value="option3">Option 3</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Constant Width Select</label>
                <Select defaultValue="optionLong">
                    <SelectTrigger className="w-full max-w-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="option1">Option 1</SelectItem>
                        <SelectItem value="option2">Option 2</SelectItem>
                        <SelectItem value="optionLong">Option 3 is too long and it will overflow the width but that's ok since this is an example.</SelectItem>
                    </SelectContent>
                </Select>
            </div>
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify all 6 select trigger buttons rendered
        const selectButtons = await canvas.findAllByRole("combobox");
        expect(selectButtons).toHaveLength(6);
    },
};
