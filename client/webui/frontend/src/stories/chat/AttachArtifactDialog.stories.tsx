import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, waitFor, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { useState } from "react";

import { AttachArtifactDialog } from "@/lib/components/chat/file/AttachArtifactDialog";

// Render the dialog open by default — the play test exercises the list, not
// the trigger flow (that path is covered by ChatInputArea stories).
const HostedDialog = () => {
    const [open] = useState(true);
    return <AttachArtifactDialog isOpen={open} onClose={() => {}} onAttach={() => {}} />;
};

const meta = {
    title: "Chat/AttachArtifactDialog",
    component: HostedDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Existing-artifact picker. Real IntersectionObserver in the browser project lets us drive the infinite-scroll sentinel end-to-end — jsdom can only stub the observer.",
            },
        },
    },
} satisfies Meta<typeof HostedDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

const makePage = (start: number, count: number, hasMore: boolean) => ({
    artifacts: Array.from({ length: count }, (_, i) => ({
        filename: `file-${start + i}.txt`,
        size: 100,
        mimeType: "text/plain",
        lastModified: "2026-01-01T00:00:00Z",
        uri: `artifact://sess-1/file-${start + i}.txt`,
        sessionId: "sess-1",
        sessionName: "Session One",
        projectId: null,
        projectName: null,
        source: null,
        tags: null,
    })),
    totalCount: hasMore ? start + count + 50 : start + count,
    hasMore,
    nextPage: hasMore ? Math.floor(start / count) + 2 : null,
});

export const InfiniteScrollLoadsNextPage: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/artifacts/all", ({ request }) => {
                    const url = new URL(request.url);
                    const page = Number(url.searchParams.get("pageNumber") ?? "1");
                    if (page === 1) {
                        return HttpResponse.json(makePage(1, 30, true));
                    }
                    return HttpResponse.json(makePage(31, 10, false));
                }),
            ],
        },
    },
    play: async () => {
        // The dialog renders into a Radix portal, not the canvas — query the
        // whole document.
        const root = within(document.body);

        // First page should land first.
        await root.findByText("file-1.txt");
        await root.findByText("file-30.txt");

        // Page 2 has not loaded yet.
        expect(root.queryByText("file-31.txt")).not.toBeInTheDocument();

        // Scroll the list's overflow container all the way to the bottom so
        // the trailing sentinel <li> intersects the viewport. (Calling
        // scrollIntoView on a row scrolls the page, not the inner container,
        // and Radix Dialog's portal blocks page scroll anyway.)
        const role = await root.findByRole("listbox");
        const scrollContainer = role.parentElement as HTMLElement;
        scrollContainer.scrollTop = scrollContainer.scrollHeight;

        // Real IntersectionObserver in the browser fires loadMore — the
        // second page artifacts should arrive.
        await waitFor(
            () => {
                expect(root.getByText("file-31.txt")).toBeInTheDocument();
            },
            { timeout: 5000 }
        );
    },
};
