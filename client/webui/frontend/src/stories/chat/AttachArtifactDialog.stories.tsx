import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { useState } from "react";

import { AttachArtifactDialog } from "@/lib/components/chat/file/AttachArtifactDialog";
import type { ArtifactWithSession } from "@/lib/api/artifacts";

// Render the dialog open by default — the play test exercises the list, not
// the trigger flow (that path is covered by ChatInputArea stories).
const HostedDialog = (props: { onAttach?: (a: ArtifactWithSession[]) => void }) => {
    const [open] = useState(true);
    return <AttachArtifactDialog isOpen={open} onClose={() => {}} onAttach={props.onAttach ?? (() => {})} />;
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

export const VersionPickerEncodesSelectedVersion: Story = {
    args: {
        onAttach: fn(),
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/artifacts/all", () => {
                    return HttpResponse.json({
                        artifacts: [
                            {
                                filename: "report.pdf",
                                size: 200,
                                mimeType: "application/pdf",
                                lastModified: "2026-01-01T00:00:00Z",
                                uri: "artifact://my-app/user-1/sess-1/report.pdf",
                                sessionId: "sess-1",
                                sessionName: "Session One",
                                projectId: null,
                                projectName: null,
                                source: null,
                                tags: null,
                            },
                        ],
                        totalCount: 1,
                        hasMore: false,
                        nextPage: null,
                    });
                }),
                // The per-row picker lazy-fetches versions on first open.
                http.get("*/api/v1/artifacts/:sessionId/report.pdf/versions", () => {
                    return HttpResponse.json([0, 1, 2]);
                }),
            ],
        },
    },
    play: async ({ args }) => {
        const root = within(document.body);

        const row = await root.findByText("report.pdf");
        // The row's version picker trigger is the only combobox in this dialog.
        const trigger = await root.findByRole("combobox");
        await userEvent.click(trigger);

        // After the lazy fetch, the version options materialize. Pick "Version 1".
        const v1 = await waitFor(() => root.getByText("Version 1"));
        await userEvent.click(v1);

        // Click the row to select it (selecting is independent of the picker).
        await userEvent.click(row);

        const attachBtn = await root.findByRole("button", { name: /attach 1/i });
        await userEvent.click(attachBtn);

        await waitFor(() => {
            expect(args.onAttach).toHaveBeenCalled();
        });
        const emitted = (args.onAttach as ReturnType<typeof fn>).mock.calls[0][0] as ArtifactWithSession[];
        // The selected version should be encoded onto the URI as ?version=1.
        expect(emitted[0].uri).toBe("artifact://my-app/user-1/sess-1/report.pdf?version=1");
    },
};
