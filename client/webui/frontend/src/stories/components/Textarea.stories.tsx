import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { Textarea } from "@/lib/components/ui/textarea";

const meta = {
    title: "Components/Textarea",
    component: Textarea,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The textarea component with various states",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center", padding: "2rem" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof Textarea>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    render: () => (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem", width: "400px" }}>
            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Default Textarea</label>
                <Textarea placeholder="Enter text..." />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Textarea with Value</label>
                <Textarea defaultValue="This is some longer text content that spans multiple lines and demonstrates how the textarea component handles text." />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Disabled Textarea</label>
                <Textarea disabled placeholder="Disabled textarea" defaultValue="Cannot edit this content" />
            </div>

            <div>
                <label>Readonly Textarea</label>
                <Textarea readOnly defaultValue="This is readonly content" />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Error State (aria-invalid)</label>
                <Textarea aria-invalid={true} placeholder="This field has an error" defaultValue="Invalid input content" />
            </div>

            <div>
                <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "500" }}>Large Content</label>
                <Textarea
                    defaultValue="This is a longer piece of text to demonstrate scrolling behaviour.&#10;&#10;Line 2 of content.&#10;Line 3 of content.&#10;Line 4 of content.&#10;Line 5 of content.&#10;Line 6 of content."
                    style={{ minHeight: "120px" }}
                />
            </div>
        </div>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify all 6 textarea elements rendered
        const textareas = await canvas.findAllByRole("textbox");
        expect(textareas).toHaveLength(6);
    },
};
