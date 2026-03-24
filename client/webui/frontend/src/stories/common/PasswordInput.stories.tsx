import { useState } from "react";
import { useForm } from "react-hook-form";
import { PasswordInput, FormFieldLayoutItem } from "@/lib/components/common";
import { expect, within } from "storybook/test";
import type { Meta, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/PasswordInput",
    parameters: {
        layout: "padded",
        docs: {
            description: {
                component: "Password input component with show/hide toggle button. Typically wrapped with FormFieldLayoutItem for form context.",
            },
        },
    },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Basic: Story = {
    render: () => {
        const { register } = useForm();
        const [showPassword, setShowPassword] = useState(false);

        return (
            <div className="max-w-md">
                <FormFieldLayoutItem label="Password" required>
                    <PasswordInput name="password" placeholder="Enter password" register={register} showPassword={showPassword} onToggle={() => setShowPassword(!showPassword)} />
                </FormFieldLayoutItem>
            </div>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByPlaceholderText("Enter password");

        // Check input is rendered and is password type
        await expect(input).toBeInTheDocument();
        await expect(input).toHaveAttribute("type", "password");

        // Check toggle button exists
        const toggleButton = within(input.parentElement!).getByRole("button");
        await expect(toggleButton).toBeInTheDocument();
    },
};

export const WithHelpText: Story = {
    render: () => {
        const { register } = useForm();
        const [showPassword, setShowPassword] = useState(false);

        return (
            <div className="max-w-md">
                <FormFieldLayoutItem label="New Password" required helpText="Must be at least 8 characters">
                    <PasswordInput name="newPassword" placeholder="Enter new password" register={register} showPassword={showPassword} onToggle={() => setShowPassword(!showPassword)} />
                </FormFieldLayoutItem>
            </div>
        );
    },
};

export const WithError: Story = {
    render: () => {
        const { register } = useForm();
        const [showPassword, setShowPassword] = useState(false);

        return (
            <div className="max-w-md">
                <FormFieldLayoutItem label="Password" required error={{ message: "Password is required" }}>
                    <PasswordInput name="password" placeholder="Enter password" register={register} showPassword={showPassword} onToggle={() => setShowPassword(!showPassword)} />
                </FormFieldLayoutItem>
            </div>
        );
    },
};

export const Disabled: Story = {
    render: () => {
        const { register } = useForm();
        const [showPassword, setShowPassword] = useState(false);

        return (
            <div className="max-w-md">
                <FormFieldLayoutItem label="Password" required>
                    <PasswordInput name="password" placeholder="Enter password" register={register} showPassword={showPassword} onToggle={() => setShowPassword(!showPassword)} disabled />
                </FormFieldLayoutItem>
            </div>
        );
    },
};

export const Standalone: Story = {
    render: () => {
        const { register } = useForm();
        const [showPassword, setShowPassword] = useState(false);

        return (
            <div className="max-w-md space-y-4">
                <p className="text-sm text-gray-600">Password input can also be used standalone without FormFieldLayoutItem:</p>
                <PasswordInput name="password" placeholder="Enter password" register={register} showPassword={showPassword} onToggle={() => setShowPassword(!showPassword)} />
            </div>
        );
    },
};
