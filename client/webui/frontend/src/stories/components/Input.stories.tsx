import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { Input } from "@/lib/components/ui/input";

const meta = {
    title: "Components/Input",
    component: Input,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The input component with various states",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center", padding: "2rem" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof Input>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    render: () => (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem", width: "400px" }}>
            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Default Input</label>
                <Input placeholder="Enter text..." />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Input with Value</label>
                <Input defaultValue="This is some text" />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Disabled Input</label>
                <Input disabled placeholder="Disabled input" defaultValue="Cannot edit this" />
            </div>

            <div>
                <label>Readonly Input</label>
                <Input readOnly defaultValue="This is readonly" />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Error State (aria-invalid)</label>
                <Input aria-invalid={true} placeholder="This field has an error" defaultValue="Invalid input" />
            </div>
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify all 5 input elements rendered
        const inputs = await canvas.findAllByRole("textbox");
        expect(inputs).toHaveLength(5);
    },
};
