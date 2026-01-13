import type { Meta, StoryObj } from "@storybook/react-vite";
import { ShareDialog } from "@/lib/components/projects/ShareDialog";
import type { Project, Collaborator } from "@/lib/types/projects";
import { http, HttpResponse, delay } from "msw";
import { expect, userEvent, within, waitFor } from "storybook/test";
import { Button } from "@/lib/components/ui/button";

// Mock Project Data
const mockProject: Project = {
    id: "p123",
    name: "My Awesome Agent",
    userId: "user1",
    description: "A project for testing sharing functionality",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    role: "owner",
};

const mockCollaborators: Collaborator[] = [
    {
        userId: "user2",
        email: "alice@example.com",
        role: "editor",
        addedAt: new Date("2024-01-15").toISOString(),
    },
    {
        userId: "user3",
        email: "bob@example.com",
        role: "viewer",
        addedAt: new Date("2024-01-20").toISOString(),
    },
];

const meta: Meta<typeof ShareDialog> = {
    title: "Projects/ShareDialog",
    component: ShareDialog,
    decorators: [
        Story => (
            <div className="flex justify-center bg-slate-50 p-12">
                <Story />
            </div>
        ),
    ],
};

export default meta;
type Story = StoryObj<typeof ShareDialog>;

// Default handlers for most stories
const defaultHandlers = [
    http.get("*/api/v1/projects/p123/collaborators", () => {
        return HttpResponse.json({ collaborators: [] });
    }),
];

export const Default: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: { handlers: defaultHandlers },
        docs: {
            description: {
                story: "ShareDialog with no collaborators. Click the Share button to open the dialog.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Verify share button is visible
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        expect(shareButton).toBeInTheDocument();

        // Click to open dialog
        await user.click(shareButton);

        // Wait for dialog to open
        const dialog = await within(document.body).findByRole("dialog");
        expect(dialog).toBeInTheDocument();

        const dialogContent = within(dialog);

        // Verify dialog title
        await dialogContent.findByText("Share Project");

        // Verify form elements
        expect(dialogContent.getByLabelText("Email address")).toBeInTheDocument();
        expect(dialogContent.getByLabelText("Role")).toBeInTheDocument();

        // Verify no collaborators message
        await dialogContent.findByText("No collaborators yet. Invite someone above!");
    },
};

export const DisabledForViewer: Story = {
    args: {
        project: {
            ...mockProject,
            role: "viewer",
        },
    },
    parameters: {
        msw: { handlers: defaultHandlers },
        docs: {
            description: {
                story: "Viewers cannot share projects, so the ShareDialog should not render at all.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify share button does NOT exist for viewers
        expect(canvas.queryByRole("button", { name: /share/i })).not.toBeInTheDocument();
    },
};

export const LoadingCollaborators: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", async () => {
                    await delay(2000);
                    return HttpResponse.json({ collaborators: [] });
                }),
            ],
        },
        docs: {
            description: {
                story: "ShareDialog showing loading state while fetching collaborators.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Verify loading state
        await dialogContent.findByText("Loading...");
    },
};

export const ShareProjectSuccess: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: [] });
                }),
                http.post("*/api/v1/projects/p123/share", async () => {
                    return HttpResponse.json({
                        userId: "user4",
                        email: "charlie@example.com",
                        role: "editor",
                        addedAt: new Date().toISOString(),
                    });
                }),
            ],
        },
        docs: {
            description: {
                story: "Successfully sharing a project with a new collaborator.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Wait for the form to be ready
        const emailInput = await dialogContent.findByLabelText("Email address");

        // Click on the input to focus it first
        await user.click(emailInput);

        // Type the email
        await user.keyboard("charlie@example.com");

        // Click submit button (the one with UserPlus icon)
        const submitButton = dialogContent.getByRole("button", { name: /invite/i });
        await user.click(submitButton);

        // Verify success message
        await waitFor(async () => {
            await dialogContent.findByText("Invitation sent to charlie@example.com");
        });
    },
};

export const ShareProjectError: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: [] });
                }),
                http.post("*/api/v1/projects/p123/share", () => {
                    return HttpResponse.json({ message: "User already has access to this project" }, { status: 400 });
                }),
            ],
        },
        docs: {
            description: {
                story: "Error handling when sharing fails (e.g., user already exists).",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Wait for the form to be ready
        const emailInput = await dialogContent.findByLabelText("Email address");

        // Click on the input to focus it first
        await user.click(emailInput);

        // Type the email
        await user.keyboard("alice@example.com");

        // Submit
        const submitButton = dialogContent.getByRole("button", { name: /invite/i });
        await user.click(submitButton);

        // Verify error message is shown
        await waitFor(async () => {
            await dialogContent.findByText(/User already has access to this project/i);
        });
    },
};

export const RemoveCollaborator: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: mockCollaborators });
                }),
                http.delete("*/api/v1/projects/p123/collaborators/user2", () => {
                    return new HttpResponse(null, { status: 204 });
                }),
            ],
        },
        docs: {
            description: {
                story: "Removing a collaborator from the project with confirmation dialog.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Wait for collaborators to load
        await dialogContent.findByText("alice@example.com");

        // Find remove buttons (trash icons)
        const removeButtons = dialogContent.getAllByRole("button", { name: /remove/i });
        await user.click(removeButtons[0]);

        // Wait for confirmation dialog to appear
        await waitFor(async () => {
            const confirmTitle = await within(document.body).findByText("Remove Collaborator");
            expect(confirmTitle).toBeInTheDocument();
        });

        // Find the confirmation dialog by looking for its specific content
        const bodyContent = within(document.body);

        // Verify confirmation dialog has the correct title and content
        await bodyContent.findByText("Remove Collaborator");
        await bodyContent.findByText(/Are you sure you want to remove/);

        // Get all Remove buttons - there should be 2 now (one in the table, one in confirmation)
        const allRemoveButtons = bodyContent.getAllByRole("button", { name: /remove/i });

        // The last one should be the confirmation button
        const confirmButton = allRemoveButtons[allRemoveButtons.length - 1];
        await user.click(confirmButton);
    },
};

export const WithCustomTrigger: Story = {
    render: () => {
        return <ShareDialog project={mockProject} trigger={<Button variant="ghost">Custom Share Trigger</Button>} />;
    },
    parameters: {
        msw: { handlers: defaultHandlers },
        docs: {
            description: {
                story: "ShareDialog with a custom trigger button.",
            },
        },
    },
};

export const TypeaheadMode: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: { handlers: defaultHandlers },
        docs: {
            description: {
                story: "ShareDialog in typeahead mode with empty search input. Toggle the switch to enable typeahead mode.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Find and toggle the switch to enable typeahead mode
        const switchElement = dialogContent.getByRole("switch");
        await user.click(switchElement);

        // Verify typeahead mode is active
        await dialogContent.findByText("Search Users");
        await dialogContent.findByPlaceholderText("Search by name or email...");
    },
};

export const TypeaheadWithResults: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: [] });
                }),
                http.get("*/api/v1/people/search*", () => {
                    return HttpResponse.json({
                        data: [
                            { id: "user4", name: "Alice Johnson", email: "alice.johnson@example.com", title: "Software Engineer" },
                            { id: "user5", name: "Bob Smith", email: "bob.smith@example.com", title: "Product Manager" },
                            { id: "user6", name: "Carol White", email: "carol.white@example.com", title: "Designer" },
                            { id: "user7", name: "David Brown", email: "david.brown@example.com", title: null },
                        ],
                    });
                }),
            ],
        },
        docs: {
            description: {
                story: "ShareDialog in typeahead mode showing search results. Type in the search box to see users.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Toggle to typeahead mode
        const switchElement = dialogContent.getByRole("switch");
        await user.click(switchElement);

        // Wait for typeahead mode to be active
        const searchInput = await dialogContent.findByPlaceholderText("Search by name or email...");

        // Type to trigger search
        await user.click(searchInput);
        await user.keyboard("ali");

        // Wait for search results to appear
        await waitFor(async () => {
            await within(document.body).findByText("Alice Johnson");
        });
    },
};

export const TypeaheadWithPending: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: [] });
                }),
                http.get("*/api/v1/people/search*", () => {
                    return HttpResponse.json({
                        data: [
                            { id: "user4", name: "Alice Johnson", email: "alice.johnson@example.com", title: "Software Engineer" },
                            { id: "user5", name: "Bob Smith", email: "bob.smith@example.com", title: "Product Manager" },
                            { id: "user6", name: "Carol White", email: "carol.white@example.com", title: "Designer" },
                        ],
                    });
                }),
            ],
        },
        docs: {
            description: {
                story: "ShareDialog in typeahead mode with pending users ready to be invited.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Toggle to typeahead mode
        const switchElement = dialogContent.getByRole("switch");
        await user.click(switchElement);

        // Wait for typeahead mode to be active
        const searchInput = await dialogContent.findByPlaceholderText("Search by name or email...");

        // Search and add first user
        await user.click(searchInput);
        await user.keyboard("ali");

        // Wait for results and click first user
        await waitFor(async () => {
            const aliceButton = await within(document.body).findByText("Alice Johnson");
            await user.click(aliceButton);
        });

        // Search and add second user
        await user.click(searchInput);
        await user.keyboard("bob");

        await waitFor(async () => {
            const bobButton = await within(document.body).findByText("Bob Smith");
            await user.click(bobButton);
        });

        // Verify pending users section appears
        await dialogContent.findByText(/Pending Invitations \(2\)/);
        await dialogContent.findByText("Alice Johnson");
        await dialogContent.findByText("Bob Smith");
    },
};

export const TypeaheadNoResults: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/projects/p123/collaborators", () => {
                    return HttpResponse.json({ collaborators: [] });
                }),
                http.get("*/api/v1/people/search*", () => {
                    return HttpResponse.json({ data: [] });
                }),
            ],
        },
        docs: {
            description: {
                story: "ShareDialog in typeahead mode showing 'No users found' message when search returns no results.",
            },
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const user = userEvent.setup({ pointerEventsCheck: 0 });

        // Open dialog
        const shareButton = await canvas.findByRole("button", { name: /share/i });
        await user.click(shareButton);

        const dialog = await within(document.body).findByRole("dialog");
        const dialogContent = within(dialog);

        // Toggle to typeahead mode
        const switchElement = dialogContent.getByRole("switch");
        await user.click(switchElement);

        // Wait for typeahead mode to be active
        const searchInput = await dialogContent.findByPlaceholderText("Search by name or email...");

        // Type to trigger search
        await user.click(searchInput);
        await user.keyboard("xyz123");

        // Wait for "No users found" message
        await waitFor(async () => {
            await within(document.body).findByText("No users found");
        });
    },
};
