import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { ShareProjectDialog } from "@/lib";
import { mockProject, mockEmptyProject, mockSharesResponse, mockEmptySharesResponse, mockPeopleSearchResponse } from "@/stories/data/projectShares";
import { withIdentityService, withoutIdentityService } from "@/stories/data/parameters";

// ============================================================================
// MSW Handlers
// ============================================================================

const defaultHandlers = [
    http.get("*/api/v1/projects/*/shares", () => {
        return HttpResponse.json(mockSharesResponse);
    }),
];

const emptySharesHandlers = [
    http.get("*/api/v1/projects/project-empty/shares", () => {
        return HttpResponse.json(mockEmptySharesResponse);
    }),
];

const withPeopleSearchHandlers = [
    http.get("*/api/v1/projects/*/shares", () => {
        return HttpResponse.json(mockSharesResponse);
    }),
    http.get("*/api/v1/identity/people*", () => {
        return HttpResponse.json(mockPeopleSearchResponse);
    }),
];

// ============================================================================
// Story Configuration
// ============================================================================

const meta = {
    title: "Pages/Projects/ShareProjectDialog",
    component: ShareProjectDialog,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "Dialog for sharing a project with other users. Supports both identity service search (with UserTypeahead) and manual email entry modes.",
            },
        },
        msw: { handlers: defaultHandlers },
    },
} satisfies Meta<typeof ShareProjectDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

// ============================================================================
// Stories
// ============================================================================

/**
 * Default state with dialog open and existing shares loaded
 */
export const Default: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Dialog will close"),
        project: mockProject,
    },
    parameters: {
        msw: { handlers: defaultHandlers },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("Share Project")).toBeInTheDocument();
        expect(await dialogContent.findByText(/Test Project/)).toBeInTheDocument();

        expect(await dialogContent.findByText("owner@example.com")).toBeInTheDocument();

        const addButton = await dialogContent.findByRole("button", { name: /Add/ });
        expect(addButton).toBeEnabled();
    },
};

/**
 * With identity service configured - shows UserTypeahead with search functionality
 */
export const WithIdentityService: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Dialog will close"),
        project: mockProject,
    },
    parameters: {
        ...withIdentityService("okta"),
        msw: { handlers: withPeopleSearchHandlers },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const addButton = await dialogContent.findByRole("button", { name: /Add/ });
        await userEvent.click(addButton);

        const searchInput = await dialogContent.findByPlaceholderText("Search by email...");
        expect(searchInput).toBeInTheDocument();
    },
};

/**
 * Without identity service - shows manual email Input field
 */
export const WithoutIdentityService: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Dialog will close"),
        project: mockProject,
    },
    parameters: {
        ...withoutIdentityService,
        msw: { handlers: defaultHandlers },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        const addButton = await dialogContent.findByRole("button", { name: /Add/ });
        await userEvent.click(addButton);

        const emailInput = await dialogContent.findByPlaceholderText("Enter email address...");
        expect(emailInput).toBeInTheDocument();
    },
};

/**
 * With existing shares - shows owner row and viewer rows with appropriate badges
 */
export const WithExistingShares: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Dialog will close"),
        project: mockProject,
    },
    parameters: {
        msw: { handlers: defaultHandlers },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("owner@example.com")).toBeInTheDocument();
        const ownerBadge = await dialogContent.findByText("Owner");
        expect(ownerBadge).toBeInTheDocument();

        expect(await dialogContent.findByText("viewer1@example.com")).toBeInTheDocument();
        const viewerBadges = await dialogContent.findAllByText("Viewer");
        expect(viewerBadges.length).toBeGreaterThan(0);
    },
};

/**
 * Empty state - no existing shares, only owner displayed.
 * Uses a separate project ID to avoid React Query cache conflicts with other stories.
 */
export const EmptyState: Story = {
    args: {
        isOpen: true,
        onClose: () => alert("Dialog will close"),
        project: mockEmptyProject,
    },
    parameters: {
        msw: { handlers: emptySharesHandlers },
    },
    play: async () => {
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("owner@example.com")).toBeInTheDocument();
        expect(await dialogContent.findByText("Owner")).toBeInTheDocument();

        expect(dialogContent.queryByText("viewer1@example.com")).toBeNull();
    },
};
