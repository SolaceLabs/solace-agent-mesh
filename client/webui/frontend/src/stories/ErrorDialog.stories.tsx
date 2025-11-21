import { useState } from "react";
import { ErrorDialog } from "@/lib";
import { Button } from "@/lib/components/ui/button";
import { expect, userEvent, within, screen } from "storybook/test";
import type { Meta, StoryContext, StoryFn } from "@storybook/react-vite";

const meta = {
    title: "Common/ErrorDialog",
    component: ErrorDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "An error dialog component for displaying error messages with optional details",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof ErrorDialog>;

export default meta;

export const Default = {
    render: () => {
        const [open, setOpen] = useState(true);

        return <ErrorDialog title="Default Error" error="Something went wrong" open={open} onOpenChange={setOpen} />;
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);
        await dialogContent.findByText("Default Error");
        await dialogContent.findByText("Something went wrong");
        await dialogContent.findByRole("button", { name: "Close" });
    },
};

export const WithErrorDetails = {
    render: () => {
        const [open, setOpen] = useState(true);

        return <ErrorDialog title="Detailed Error" error="Something went wrong" errorDetails="This action is forbidden. Ensure you have the right authorization." open={open} onOpenChange={setOpen} />;
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);
        await dialogContent.findByText("Detailed Error");
        await dialogContent.findByText("Something went wrong");
        // check detailed error message
        await dialogContent.findByText(/This action is forbidden/);
        await dialogContent.findByRole("button", { name: "Close" });
    },
};

export const WithButton = {
    render: () => {
        const [open, setOpen] = useState(false);

        return (
            <>
                <Button onClick={() => setOpen(true)} variant="destructive">
                    Show Error Dialog
                </Button>
                <ErrorDialog
                    title="Long Detailed Error"
                    error="Something went wrong"
                    errorDetails="This action is cannot be performed due to some very long reason that needs to wrap in this dialog for demonstration purposes."
                    open={open}
                    onOpenChange={setOpen}
                />
            </>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // click trigger button
        await userEvent.click(await canvas.findByText("Show Error Dialog"));

        const dialog = await screen.findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);
        await dialogContent.findByText("Long Detailed Error");
        await dialogContent.findByText("Something went wrong");
        // check detailed error message
        await dialogContent.findByText("This action is cannot be performed due to some very long reason that needs to wrap in this dialog for demonstration purposes.");
        await dialogContent.findByRole("button", { name: "Close" });
    },
};
