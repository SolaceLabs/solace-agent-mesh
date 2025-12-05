import { useState } from "react";
import type { Meta, StoryContext, StoryFn } from "@storybook/react-vite";
import { SettingsDialog } from "@/lib/components/settings/SettingsDialog";
import { NavigationList } from "@/lib/components/navigation/NavigationList";
import { expect, userEvent, within } from "storybook/test";

const meta = {
    title: "Views/Settings",
    component: SettingsDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "A settings dialog component with multiple sections for configuring application settings, shown in the context of NavigationList",
            },
        },
        configContext: {
            persistenceEnabled: false,
            frontend_use_authorization: false,
            configFeatureEnablement: {
                speechToText: false,
                textToSpeech: false,
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof SettingsDialog>;

export default meta;

export const Default = {
    render: () => {
        const [activeItem, setActiveItem] = useState<string | null>(null);

        return (
            <div style={{ width: "100px", height: "100%", backgroundColor: "var(--color-primary-w100)", display: "flex", flexDirection: "column" }}>
                <NavigationList items={[]} activeItem={activeItem} onItemClick={(itemId: string) => setActiveItem(itemId)} />
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // Find and click the Settings button
        const settingsButton = await canvas.findByLabelText("Open Settings");
        await userEvent.click(settingsButton);

        // Verify the dialog opened
        const dialog = await within(document.body).findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        // Verify dialog content
        const dialogContent = within(dialog);
        await dialogContent.findByRole("button", { name: "General" });
        await dialogContent.findByRole("button", { name: "About" });
        expect(dialogContent.queryByRole("button", { name: "Speech" })).toBeNull();
    },
};

export const About = {
    render: () => {
        const [activeItem, setActiveItem] = useState<string | null>(null);

        return (
            <div style={{ width: "100px", height: "100%", backgroundColor: "var(--color-primary-w100)", display: "flex", flexDirection: "column" }}>
                <NavigationList items={[]} activeItem={activeItem} onItemClick={(itemId: string) => setActiveItem(itemId)} />
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // Find and click the Settings button
        const settingsButton = await canvas.findByLabelText("Open Settings");
        await userEvent.click(settingsButton);

        // Verify the dialog opened
        const dialog = await within(document.body).findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        // Verify dialog content
        const dialogContent = within(dialog);
        await dialogContent.findByRole("button", { name: "General" });
        const about = await dialogContent.findByRole("button", { name: "About" });

        await userEvent.click(about);
        await dialogContent.findByText("Application Versions");
    },
};

export const TextToSpeech = {
    parameters: {
        configContext: {
            persistenceEnabled: false,
            frontend_use_authorization: false,
            configFeatureEnablement: {
                speechToText: false,
                textToSpeech: true,
            },
        },
    },
    render: () => {
        const [activeItem, setActiveItem] = useState<string | null>(null);

        return (
            <div style={{ width: "100px", height: "100%", backgroundColor: "var(--color-primary-w100)", display: "flex", flexDirection: "column" }}>
                <NavigationList items={[]} activeItem={activeItem} onItemClick={(itemId: string) => setActiveItem(itemId)} />
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // Find and click the Settings button
        const settingsButton = await canvas.findByLabelText("Open Settings");
        await userEvent.click(settingsButton);

        // Verify the dialog opened
        const dialog = await within(document.body).findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        // Verify dialog content
        const dialogContent = within(dialog);
        await dialogContent.findByRole("button", { name: "General" });
        await dialogContent.findByRole("button", { name: "About" });
        const speech = await dialogContent.findByRole("button", { name: "Speech" });

        await userEvent.click(speech);
        await dialogContent.findByText("Text-to-Speech");
        expect(dialogContent.queryByText("Speech-to-Text")).toBeNull();
    },
};

export const Logout = {
    parameters: {
        configContext: {
            persistenceEnabled: false,
            frontend_use_authorization: true,
            configFeatureEnablement: {
                speechToText: false,
                textToSpeech: false,
            },
        },
    },
    render: () => {
        const [activeItem, setActiveItem] = useState<string | null>(null);

        return (
            <div style={{ width: "100px", height: "100%", backgroundColor: "var(--color-primary-w100)", display: "flex", flexDirection: "column" }}>
                <NavigationList items={[]} activeItem={activeItem} onItemClick={(itemId: string) => setActiveItem(itemId)} />
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // When authorization is enabled, Settings becomes a menu item
        const menu = await canvas.findByLabelText("Open Menu");
        await expect(menu).toBeInTheDocument();

        await userEvent.click(menu);

        await within(document.body).findByRole("menuitem", { name: "Settings" });
        const logoutButton = await within(document.body).findByRole("menuitem", { name: "Logout" });
        await expect(logoutButton).toBeInTheDocument();
    },
};

export const All = {
    parameters: {
        configContext: {
            persistenceEnabled: false,
            frontend_use_authorization: true,
            configFeatureEnablement: {
                speechToText: true,
                textToSpeech: true,
            },
        },
    },
    render: () => {
        const [activeItem, setActiveItem] = useState<string | null>(null);

        return (
            <div style={{ width: "100px", height: "100%", backgroundColor: "var(--color-primary-w100)", display: "flex", flexDirection: "column" }}>
                <NavigationList items={[]} activeItem={activeItem} onItemClick={(itemId: string) => setActiveItem(itemId)} />
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);

        // When authorization is enabled, Settings becomes a menu item
        const menu = await canvas.findByLabelText("Open Menu");
        await expect(menu).toBeInTheDocument();

        await userEvent.click(menu);

        await within(document.body).findByRole("menuitem", { name: "Logout" });
        const settingsButton = await within(document.body).findByRole("menuitem", { name: "Settings" });
        await expect(settingsButton).toBeInTheDocument();
        await userEvent.click(settingsButton);

        // Verify the dialog opened
        const dialog = await within(document.body).findByRole("dialog");
        await expect(dialog).toBeInTheDocument();

        // Verify Speech tab is available and shows both features
        const dialogContent = within(dialog);
        const speech = await dialogContent.findByRole("button", { name: "Speech" });
        await userEvent.click(speech);
        await dialogContent.findByText("Speech-to-Text");
        await dialogContent.findByText("Text-to-Speech");
    },
};
