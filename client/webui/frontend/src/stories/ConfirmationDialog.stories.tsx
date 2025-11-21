import { useState } from "react";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import { Button } from "@/lib/components/ui/button";
import { expect, userEvent, within, screen } from "storybook/test";
import type { Meta, StoryContext, StoryFn } from "@storybook/react-vite";

const meta = {
    title: "Common/ConfirmationDialog",
    component: ConfirmationDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "A confirmation dialog component with customizable title, message, and actions",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof ConfirmationDialog>;

export default meta;

export const Default = {
    render: () => {
        const [open, setOpen] = useState(true);

        return <ConfirmationDialog title="Confirm Dialog" content="Are you sure you want to do this action?" onConfirm={() => alert("Action confirmed")} open={open} onOpenChange={setOpen} />;
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);
        // check title
        await dialogContent.findByText("Confirm Dialog");
        // check message
        await dialogContent.findByText("Are you sure you want to do this action?");
        await dialogContent.findByRole("button", { name: "Cancel" });
        await dialogContent.findByRole("button", { name: "Confirm" });
    },
};

export const WithTrigger = {
    render: () => {
        const [open, setOpen] = useState(false);

        return <ConfirmationDialog title="Confirm Dialog" trigger={<Button variant="outline">Trigger</Button>} content="Are you sure you want to do this action?" onConfirm={() => alert("Action confirmed")} open={open} onOpenChange={setOpen} />;
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // click trigger button
        await userEvent.click(await canvas.findByText("Trigger"));

        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);
        // check title
        await dialogContent.findByText("Confirm Dialog");
        await dialogContent.findByRole("button", { name: "Cancel" });
        await dialogContent.findByRole("button", { name: "Confirm" });
    },
};

export const WithExternalButton = {
    render: () => {
        const [open, setOpen] = useState(false);

        return (
            <>
                <Button onClick={() => setOpen(true)}>External Button</Button>
                <ConfirmationDialog title="Confirm Dialog With External Button" content="Are you sure you want to do this action?" onConfirm={() => alert("Action confirmed")} open={open} onOpenChange={setOpen} />
            </>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // click external button
        await userEvent.click(await canvas.findByText("External Button"));

        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);
        await dialogContent.findByRole("button", { name: "Cancel" });
        await dialogContent.findByRole("button", { name: "Confirm" });
    },
};
