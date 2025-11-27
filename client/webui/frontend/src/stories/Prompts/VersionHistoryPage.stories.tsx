import { VersionHistoryPage } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { http, HttpResponse } from "msw";
import { weatherPromptGroup, defaultVersions } from "./data";
import { expect, within } from "storybook/test";

const handlers = [
    http.get(`*/api/v1/prompts/groups/${weatherPromptGroup.id}/prompts`, () => {
        return HttpResponse.json(defaultVersions);
    }),
];

const meta = {
    title: "Pages/Prompts/VersionHistoryPage",
    component: VersionHistoryPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The component for templating and building custom prompts",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof VersionHistoryPage>;

export default meta;
type Story = StoryObj<typeof VersionHistoryPage>;

export const Default: Story = {
    args: {
        group: weatherPromptGroup,
    },
    parameters: {
        msw: { handlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        for (const version of defaultVersions) {
            const versionElem = await canvas.findByTestId(version.id);
            expect(versionElem).toBeVisible();
        }
    },
};
