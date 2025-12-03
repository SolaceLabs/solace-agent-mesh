import { Menu } from "@/lib/components/ui/menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/lib/components/ui/popover";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/Menu",
    component: Menu,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The menu component",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return (
                <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center" }}>
                    <Popover defaultOpen>
                        <PopoverTrigger asChild>
                            <button style={{ visibility: "hidden" }}>Trigger</button>
                        </PopoverTrigger>
                        <PopoverContent align="center" side="bottom" className="w-auto" sideOffset={0}>
                            {storyResult}
                        </PopoverContent>
                    </Popover>
                </div>
            );
        },
    ],
} satisfies Meta<typeof Menu>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        actions: [
            { id: "action-1", label: "Name A-Z", onClick: () => alert("Sorts by Names by A-Z") },
            { id: "action-2", label: "Name Z-A", onClick: () => alert("Sorts by Names by Z-A") },
            { id: "action-3", label: "Date (Oldest first)", onClick: () => alert("Sorts by Oldest Dates First") },
            { id: "action-4", label: "Date (Newest first)", onClick: () => alert("Sorts by Newest Dates First") },
        ],
    },
};

export const DisabledOptions: Story = {
    args: {
        actions: [
            { id: "action-1", label: "Name A-Z", onClick: () => alert("Sorts by Names by A-Z"), disabled: true },
            { id: "action-2", label: "Name Z-A", onClick: () => alert("Sorts by Names by Z-A") },
            { id: "action-3", label: "Date (Oldest first)", onClick: () => alert("Sorts by Oldest Dates First") },
            { id: "action-4", label: "Date (Newest first)", onClick: () => alert("Sorts by Newest Dates First") },
        ],
    },
};
