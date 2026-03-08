import { defineStepper, type StepperVariant, type StepperLabelOrientation } from "@/lib/components/ui/stepper";
import { Button } from "@/lib/components/ui/button";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";

// Define the steps for the stepper
const { Stepper } = defineStepper({ id: "step1", title: "Step 1", description: "First step" }, { id: "step2", title: "Step 2", description: "Second step" }, { id: "step3", title: "Step 3", description: "Third step" });

// Example Stepper Implementation Component
const StepperExample = ({ variant = "horizontal", labelOrientation = "horizontal" }: { variant?: StepperVariant; labelOrientation?: StepperLabelOrientation }) => {
    return (
        <Stepper.Provider variant={variant} labelOrientation={labelOrientation}>
            {({ methods }) => (
                <>
                    <Stepper.Navigation>
                        <Stepper.Step of="step1">
                            <Stepper.Title>Account</Stepper.Title>
                            <Stepper.Description>Create your account</Stepper.Description>
                        </Stepper.Step>
                        <Stepper.Step of="step2">
                            <Stepper.Title>Profile</Stepper.Title>
                            <Stepper.Description>Set up your profile</Stepper.Description>
                        </Stepper.Step>
                        <Stepper.Step of="step3">
                            <Stepper.Title>Complete</Stepper.Title>
                            <Stepper.Description>Review and finish</Stepper.Description>
                        </Stepper.Step>
                    </Stepper.Navigation>

                    <div style={{ marginTop: "2rem" }}>
                        <Stepper.Panel>
                            <div style={{ padding: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}>
                                <h3>Step Content: {methods.current.title}</h3>
                                <p>{methods.current.description}</p>
                            </div>
                        </Stepper.Panel>
                    </div>

                    <Stepper.Controls style={{ marginTop: "1rem" }}>
                        <Button onClick={methods.prev} disabled={methods.current.id === "step1"}>
                            Previous
                        </Button>
                        <Button onClick={methods.next} disabled={methods.current.id === "step3"}>
                            Next
                        </Button>
                    </Stepper.Controls>
                </>
            )}
        </Stepper.Provider>
    );
};

const meta = {
    title: "Common/Stepper",
    component: StepperExample,
    parameters: {
        layout: "centered",
        docs: {
            description: {
                component: "A stepper component for multi-step workflows with support for horizontal, vertical, and circle variants.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return (
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minHeight: "400px",
                        minWidth: "600px",
                        padding: "2rem",
                    }}
                >
                    {storyResult}
                </div>
            );
        },
    ],
} satisfies Meta<typeof StepperExample>;

export default meta;

type Story = StoryObj<typeof meta>;

export const HorizontalDefault: Story = {
    args: {
        variant: "horizontal",
        labelOrientation: "horizontal",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check that navigation is rendered
        const navigation = canvas.getByRole("tablist");
        expect(navigation).toBeInTheDocument();

        // Check that all three step buttons are rendered
        const stepButtons = canvas.getAllByRole("tab");
        expect(stepButtons).toHaveLength(3);

        // Check that step titles are present
        expect(canvas.getByText("Account")).toBeInTheDocument();
        expect(canvas.getByText("Profile")).toBeInTheDocument();
        expect(canvas.getByText("Complete")).toBeInTheDocument();

        // Check that control buttons are present
        expect(canvas.getByText("Previous")).toBeInTheDocument();
        expect(canvas.getByText("Next")).toBeInTheDocument();
    },
};

export const HorizontalVerticalLabels: Story = {
    args: {
        variant: "horizontal",
        labelOrientation: "vertical",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check that navigation is rendered
        const navigation = canvas.getByRole("tablist");
        expect(navigation).toBeInTheDocument();

        // Check that step titles are present
        expect(canvas.getByText("Account")).toBeInTheDocument();
        expect(canvas.getByText("Create your account")).toBeInTheDocument();
    },
};

export const Vertical: Story = {
    args: {
        variant: "vertical",
        labelOrientation: "horizontal",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check that navigation is rendered
        const navigation = canvas.getByRole("tablist");
        expect(navigation).toBeInTheDocument();

        // Check that all three steps are present
        expect(canvas.getByText("Account")).toBeInTheDocument();
        expect(canvas.getByText("Profile")).toBeInTheDocument();
        expect(canvas.getByText("Complete")).toBeInTheDocument();
    },
};

export const Circle: Story = {
    args: {
        variant: "circle",
        labelOrientation: "horizontal",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Check that navigation is rendered
        const navigation = canvas.getByRole("tablist");
        expect(navigation).toBeInTheDocument();

        // Check for progress indicators (one per step in circle variant)
        const progressIndicators = canvas.getAllByRole("progressbar");
        expect(progressIndicators).toHaveLength(3);

        // Check the first progress indicator
        expect(progressIndicators[0]).toHaveAttribute("aria-valuenow", "1");
        expect(progressIndicators[0]).toHaveAttribute("aria-valuemax", "3");
    },
};
