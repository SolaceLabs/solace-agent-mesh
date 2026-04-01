# PasswordInput Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `<encrypted>` sentinel pattern in password fields with asterisk placeholders and RHF `dirtyFields`-based dirty tracking, so credentials are omitted from the payload when unchanged.

**Architecture:** PasswordInput becomes a controlled component (via RHF `Controller`) that receives a `hasStoredValue` prop to drive placeholder UX. The parent form passes `dirtyFields` to `buildModelPayload`, which omits unchanged credential fields from the API payload. No backend changes.

**Tech Stack:** React 18, react-hook-form, Tailwind CSS, Vitest, Storybook

**Spec:** `docs/superpowers/specs/2026-03-31-password-input-redesign.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `client/webui/frontend/src/lib/components/common/PasswordInput.tsx` | Rewrite | Controlled password input with `hasStoredValue` UX |
| `client/webui/frontend/src/lib/components/models/modelProviderUtils.ts` | Modify | Update `buildModelPayload` to accept `dirtyFields`, remove sentinel constants |
| `client/webui/frontend/src/lib/components/models/ModelEdit.tsx` | Modify | Remove `showPassword` state, wire `hasStoredValue`/`control`/`dirtyFields` |
| `client/webui/frontend/src/lib/components/models/ModelEditPage.tsx` | Modify | Thread `dirtyFields` through `handleSave` |
| `client/webui/frontend/src/lib/components/models/TestConnectionSection.tsx` | Modify | Accept and pass `dirtyFields` to `buildModelPayload` |
| `client/webui/frontend/src/stories/common/PasswordInput.test.tsx` | Rewrite | Tests for new Controller-based component |
| `client/webui/frontend/src/stories/common/PasswordInput.stories.tsx` | Rewrite | Stories for new API |

---

### Task 1: Update `buildModelPayload` to accept `dirtyFields`

**Files:**
- Modify: `client/webui/frontend/src/lib/components/models/modelProviderUtils.ts:15-37` (remove constants), `:391-399` (update function)

- [ ] **Step 1: Remove sentinel constants**

In `modelProviderUtils.ts`, remove the `REDACTED_CREDENTIAL_PLACEHOLDER` constant (line 15), its JSDoc (lines 10-14), the `REDACTED_CREDENTIAL_FIELDS` constant (line 37), and its JSDoc (lines 31-36). Keep `AUTH_CONFIG_TO_FORM_FIELD_MAP` — it's still needed.

Update the section comment and the JSDoc for `AUTH_CONFIG_TO_FORM_FIELD_MAP`:

```typescript
// ============================================================================
// Auth credential field mapping
// ============================================================================

/**
 * Mapping of backend authConfig keys to form field names for sensitive credentials.
 * Used to determine which form fields have stored values during edit,
 * and to check dirtyFields when building payloads.
 */
export const AUTH_CONFIG_TO_FORM_FIELD_MAP: Record<string, string> = {
    api_key: "apiKey",
    client_id: "clientId",
    client_secret: "clientSecret",
    aws_access_key_id: "awsAccessKeyId",
    aws_secret_access_key: "awsSecretAccessKey",
    aws_session_token: "awsSessionToken",
    gcp_service_account_json: "gcpServiceAccountJson",
};
```

- [ ] **Step 2: Update `buildModelPayload` signature and remove stripping logic**

Change the function signature to accept an optional `dirtyFields` parameter. Remove the placeholder stripping loop. Update the auth config building to check `dirtyFields` before including credential fields.

Replace the entire `buildModelPayload` function (lines 391-494) with:

```typescript
/**
 * Build model params and auth config from form data.
 * Shared between save and test connection flows.
 *
 * When dirtyFields is provided, credential fields are only included in authConfig
 * if the user actually modified them (based on react-hook-form's dirtyFields).
 * This prevents sending empty strings for unchanged credentials.
 */
export function buildModelPayload(data: ModelFormData, dirtyFields?: Partial<Record<string, boolean>>) {
    const providerConfig = getProviderConfig(data.provider);

    // Collect model_params from provider-specific fields
    const modelParams: Record<string, unknown> = {};
    for (const field of providerConfig.fields) {
        if (data[field.name] != null && data[field.name] !== "") {
            const value = field.type === "number" ? Number(data[field.name]) : data[field.name];
            modelParams[field.name] = value;
        }
    }

    // Add common model params
    if (data.temperature != null && data.temperature !== "") {
        modelParams.temperature = Number(data.temperature);
    }
    if (data.maxTokens != null && data.maxTokens !== "") {
        modelParams.max_tokens = Number(data.maxTokens);
    }
    if (data.cache_strategy != null && data.cache_strategy !== "") {
        modelParams.cache_strategy = data.cache_strategy;
    }

    // Add custom parameters
    if (data.customParams && Array.isArray(data.customParams)) {
        data.customParams.forEach((param: { key: string; value: string }) => {
            if (param.key.trim()) {
                modelParams[param.key] = param.value;
            }
        });
    }

    // Helper: check if a credential field should be included in the payload.
    // If dirtyFields is provided, only include fields the user actually modified.
    // If dirtyFields is not provided (e.g., creating a new model), include all non-empty fields.
    const shouldIncludeCredential = (fieldName: string, value: unknown): boolean => {
        if (dirtyFields) {
            return !!dirtyFields[fieldName];
        }
        return !!value;
    };

    // Build auth config
    let authConfig: Record<string, unknown> = {};
    if (data.authType === "apikey") {
        authConfig = { type: "apikey" };
        if (shouldIncludeCredential("apiKey", data.apiKey)) {
            authConfig.api_key = data.apiKey;
        }
    } else if (data.authType === "oauth2") {
        authConfig = { type: "oauth2" };
        if (shouldIncludeCredential("clientId", data.clientId)) {
            authConfig.client_id = data.clientId;
        }
        if (shouldIncludeCredential("clientSecret", data.clientSecret)) {
            authConfig.client_secret = data.clientSecret;
        }
        if (data.tokenUrl) {
            authConfig.token_url = data.tokenUrl;
        }
        if (data.oauthScope) {
            authConfig.scope = data.oauthScope;
        }
        if (data.oauthTokenRefreshBufferSeconds) {
            authConfig.token_refresh_buffer_seconds = Number(data.oauthTokenRefreshBufferSeconds);
        }
    } else if (data.authType === "aws_iam") {
        authConfig = { type: "aws_iam" };
        if (shouldIncludeCredential("awsAccessKeyId", data.awsAccessKeyId)) {
            authConfig.aws_access_key_id = data.awsAccessKeyId;
        }
        if (shouldIncludeCredential("awsSecretAccessKey", data.awsSecretAccessKey)) {
            authConfig.aws_secret_access_key = data.awsSecretAccessKey;
        }
        if (shouldIncludeCredential("awsSessionToken", data.awsSessionToken)) {
            authConfig.aws_session_token = data.awsSessionToken;
        }
    } else if (data.authType === "gcp_service_account") {
        authConfig = { type: "gcp_service_account" };
        if (shouldIncludeCredential("gcpServiceAccountJson", data.gcpServiceAccountJson)) {
            authConfig.service_account_json = data.gcpServiceAccountJson;
        }
    } else {
        authConfig = { type: "none" };
    }

    // Format model name with provider prefix if needed
    let modelName = data.modelName;
    if (!modelName.includes("/") && data.provider === "custom") {
        modelName = `openai/${modelName}`;
    }

    return {
        alias: data.alias,
        provider: data.provider,
        modelName,
        apiBase: data.apiBase || null,
        description: data.description || null,
        authType: data.authType,
        authConfig,
        modelParams,
    };
}
```

- [ ] **Step 3: Remove unused imports of deleted constants**

Check if `REDACTED_CREDENTIAL_PLACEHOLDER` or `REDACTED_CREDENTIAL_FIELDS` are exported and used elsewhere. They are imported in `ModelEdit.tsx` — that import will be fixed in Task 3. No other files import them. The exports are removed by deleting the constants.

- [ ] **Step 4: Run tests to verify nothing breaks**

Run: `cd client/webui/frontend && npx vitest --project=unit --run`

Expected: All existing tests pass. The PasswordInput tests still pass since we haven't changed the component yet.

- [ ] **Step 5: Commit**

```bash
git add client/webui/frontend/src/lib/components/models/modelProviderUtils.ts
git commit -m "refactor: update buildModelPayload to use dirtyFields instead of sentinel stripping"
```

---

### Task 2: Rewrite PasswordInput component

**Files:**
- Rewrite: `client/webui/frontend/src/lib/components/common/PasswordInput.tsx`

- [ ] **Step 1: Write the new PasswordInput component**

Replace the entire file with the new controlled component:

```tsx
import { useState } from "react";
import { Controller } from "react-hook-form";
import { Eye, EyeOff } from "lucide-react";
import type { Control, FieldValues, Path } from "react-hook-form";

import { Button, Input } from "@/lib/components/ui";

export interface PasswordInputProps<T extends FieldValues = FieldValues> {
    name: Path<T>;
    control: Control<T>;
    hasStoredValue?: boolean;
    placeholder?: string;
    disabled?: boolean;
    rules?: Record<string, unknown>;
}

const STORED_VALUE_PLACEHOLDER = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

/**
 * Password input with show/hide toggle.
 *
 * When `hasStoredValue` is true and the field is empty, an asterisk placeholder
 * is shown to indicate a credential exists server-side. The eye toggle is always
 * visible (signals a sensitive field) but is inert when only the placeholder is shown.
 */
export const PasswordInput = <T extends FieldValues = FieldValues>({
    name,
    control,
    hasStoredValue = false,
    placeholder,
    disabled = false,
    rules,
}: PasswordInputProps<T>) => {
    const [showPassword, setShowPassword] = useState(false);

    return (
        <Controller
            name={name}
            control={control}
            rules={rules}
            render={({ field }) => {
                const hasUserInput = !!field.value;
                const isEyeFunctional = hasUserInput || !hasStoredValue;
                const effectivePlaceholder = hasStoredValue && !hasUserInput ? STORED_VALUE_PLACEHOLDER : placeholder;
                const inputType = showPassword && isEyeFunctional ? "text" : "password";

                return (
                    <div className="relative">
                        <Input
                            {...field}
                            value={field.value ?? ""}
                            type={inputType}
                            placeholder={effectivePlaceholder}
                            autoComplete="new-password"
                            disabled={disabled}
                            className="pr-10"
                            role="textbox"
                        />
                        <Button
                            type="button"
                            onClick={() => {
                                if (isEyeFunctional) {
                                    setShowPassword(prev => !prev);
                                }
                            }}
                            disabled={disabled}
                            variant="ghost"
                            size="sm"
                            className="pointer-events-auto absolute top-1/2 right-1 -translate-y-1/2"
                            title={showPassword && isEyeFunctional ? "Hide password" : "Show password"}
                            aria-label={showPassword && isEyeFunctional ? "Hide password" : "Show password"}
                        >
                            {showPassword && isEyeFunctional ? <EyeOff size={18} /> : <Eye size={18} />}
                        </Button>
                    </div>
                );
            }}
        />
    );
};
```

- [ ] **Step 2: Verify the barrel export still works**

Check `client/webui/frontend/src/lib/components/common/index.ts` line 21: `export { PasswordInput } from "./PasswordInput";`. No changes needed — the named export is the same.

- [ ] **Step 3: Commit**

```bash
git add client/webui/frontend/src/lib/components/common/PasswordInput.tsx
git commit -m "feat: rewrite PasswordInput as controlled component with hasStoredValue support"
```

---

### Task 3: Update ModelEdit to use new PasswordInput

**Files:**
- Modify: `client/webui/frontend/src/lib/components/models/ModelEdit.tsx`

- [ ] **Step 1: Update imports**

Remove `REDACTED_CREDENTIAL_PLACEHOLDER` from the import on line 15. Add `AUTH_CONFIG_TO_FORM_FIELD_MAP` is already imported. The updated import block from `modelProviderUtils` should be:

```typescript
import {
    getProviderConfig,
    AUTH_FIELDS,
    AUTH_TYPE_LABELS,
    COMMON_MODEL_PARAMS,
    AUTH_CONFIG_TO_FORM_FIELD_MAP,
    type AuthType,
    type ProviderField,
    type SupportedModel,
    type ModelProvider,
    type ModelFormData,
} from "./modelProviderUtils";
```

- [ ] **Step 2: Add `storedCredentialFields` state, remove `showPassword` state**

Replace:
```typescript
const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
```

With:
```typescript
const [storedCredentialFields, setStoredCredentialFields] = useState<Set<string>>(new Set());
```

This tracks which credential fields have a stored value on the server (populated during edit initialization).

- [ ] **Step 3: Update the `onSave` callback signature**

The `ModelEdit` component needs to pass `dirtyFields` alongside form data when saving. Update the `onSave` prop type and the `onFormSubmit` handler.

In the `ModelEditProps` interface, change:
```typescript
onSave: (data: ModelFormData) => Promise<void>;
```
To:
```typescript
onSave: (data: ModelFormData, dirtyFields: Partial<Record<string, boolean>>) => Promise<void>;
```

Extract `dirtyFields` from `formState` in the destructuring (add it alongside `errors`, `isDirty`, `isValid`):
```typescript
const {
    register,
    control,
    formState: { errors, isDirty, isValid, dirtyFields },
    handleSubmit,
    watch,
    setValue,
    resetField,
    getValues,
} = methods;
```

Update `onFormSubmit`:
```typescript
const onFormSubmit = async (data: ModelFormData) => {
    await onSave(data, dirtyFields);
};
```

- [ ] **Step 4: Update credential population during edit**

In the `useEffect` that populates fields from `modelToEdit` (around line 260-265), replace the `REDACTED_CREDENTIAL_PLACEHOLDER` logic:

Replace:
```typescript
// Populate auth credential fields from authConfig
// For password fields that are redacted by the server, populate with REDACTED_CREDENTIAL_PLACEHOLDER
if (modelToEdit.authConfig) {
    Object.entries(AUTH_CONFIG_TO_FORM_FIELD_MAP).forEach(([configKey, fieldName]) => {
        const value = modelToEdit.authConfig[configKey];
        // If the value is empty/falsy (redacted by server), use placeholder
        setValue(fieldName, value ? String(value) : REDACTED_CREDENTIAL_PLACEHOLDER);
    });
}
```

With:
```typescript
// Track which credential fields have stored values on the server.
// The backend redacts secrets (removes them from the response), so any key
// present in authConfig with a truthy value is a non-redacted field (like tokenUrl).
// Keys that are absent or have falsy values are redacted secrets — these are
// the fields that have stored values server-side.
if (modelToEdit.authConfig) {
    const stored = new Set<string>();
    Object.entries(AUTH_CONFIG_TO_FORM_FIELD_MAP).forEach(([configKey, fieldName]) => {
        const value = modelToEdit.authConfig[configKey];
        if (value) {
            // Non-redacted field — populate with the actual value
            setValue(fieldName, String(value));
        } else {
            // Redacted by server — mark as having a stored value
            stored.add(fieldName);
        }
    });
    setStoredCredentialFields(stored);
}
```

- [ ] **Step 5: Update `isAuthCredentialsConfigured` to account for stored values**

The `isAuthCredentialsConfigured` computed value (lines 84-104) currently checks that credentials aren't equal to `REDACTED_CREDENTIAL_PLACEHOLDER`. Replace it with logic that treats stored credentials as configured:

```typescript
const isAuthCredentialsConfigured = (() => {
    if (!selectedAuthType) return false;
    if (selectedAuthType === "none") return true;

    // When editing, stored credentials count as "configured"
    const isConfigured = (fieldName: string) => {
        return !!getValues(fieldName) || storedCredentialFields.has(fieldName);
    };

    if (selectedAuthType === "apikey") return isConfigured("apiKey");
    if (selectedAuthType === "oauth2") {
        return isConfigured("clientId") && isConfigured("clientSecret") && !!getValues("tokenUrl");
    }
    if (selectedAuthType === "aws_iam") {
        return isConfigured("awsAccessKeyId") && isConfigured("awsSecretAccessKey");
    }
    if (selectedAuthType === "gcp_service_account") {
        return isConfigured("gcpServiceAccountJson");
    }
    return false;
})();
```

- [ ] **Step 6: Update `renderField` for password fields**

In the `renderField` function, update the password field rendering to use the new PasswordInput API. Replace the password field block (around lines 321-327):

Replace:
```typescript
if (field.type === "password") {
    return (
        <FormFieldLayoutItem key={field.name} label={field.label} required={isRequiredField} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
            <PasswordInput name={field.name} register={register} placeholder={field.placeholder} showPassword={showPassword[field.name] || false} onToggle={() => setShowPassword(prev => ({ ...prev, [field.name]: !prev[field.name] }))} />
        </FormFieldLayoutItem>
    );
}
```

With:
```typescript
if (field.type === "password") {
    return (
        <FormFieldLayoutItem key={field.name} label={field.label} required={isRequiredField} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
            <PasswordInput
                name={field.name}
                control={control}
                hasStoredValue={storedCredentialFields.has(field.name)}
                placeholder={field.placeholder}
                rules={{ required: isRequiredField ? `${field.label} is required` : false }}
            />
        </FormFieldLayoutItem>
    );
}
```

- [ ] **Step 7: Update `TestConnectionSection` props to include `dirtyFields`**

In `ModelEdit.tsx`, the `TestConnectionSection` is rendered with `getFormData={() => getValues() as ModelFormData}`. We also need to pass `dirtyFields` so test connection can use it. Update the TestConnectionSection rendering:

Replace:
```typescript
<TestConnectionSection getFormData={() => getValues() as ModelFormData} isNew={isNew} modelAlias={modelToEdit?.alias} disabled={!selectedProvider || !selectedModelName || (isNew && !isAuthCredentialsConfigured)} />
```

With:
```typescript
<TestConnectionSection getFormData={() => getValues() as ModelFormData} getDirtyFields={() => dirtyFields} isNew={isNew} modelAlias={modelToEdit?.alias} disabled={!selectedProvider || !selectedModelName || (isNew && !isAuthCredentialsConfigured)} />
```

- [ ] **Step 8: Commit**

```bash
git add client/webui/frontend/src/lib/components/models/ModelEdit.tsx
git commit -m "refactor: update ModelEdit to use new PasswordInput with dirtyFields tracking"
```

---

### Task 4: Update ModelEditPage and TestConnectionSection

**Files:**
- Modify: `client/webui/frontend/src/lib/components/models/ModelEditPage.tsx`
- Modify: `client/webui/frontend/src/lib/components/models/TestConnectionSection.tsx`

- [ ] **Step 1: Update `handleSave` in ModelEditPage**

In `ModelEditPage.tsx`, update `handleSave` to accept and pass `dirtyFields`:

Replace:
```typescript
const handleSave = async (data: ModelFormData) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
        const payload = buildModelPayload(data);
```

With:
```typescript
const handleSave = async (data: ModelFormData, dirtyFields?: Partial<Record<string, boolean>>) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
        const payload = buildModelPayload(data, dirtyFields);
```

Also remove `REDACTED_CREDENTIAL_PLACEHOLDER` and `REDACTED_CREDENTIAL_FIELDS` from the import if present. The current import is:
```typescript
import { ALL_PROVIDERS, buildModelPayload } from "./modelProviderUtils";
```
This doesn't import the sentinel constants, so no change needed here.

- [ ] **Step 2: Update TestConnectionSection to accept `getDirtyFields`**

In `TestConnectionSection.tsx`, add `getDirtyFields` to the props and pass it through to `buildModelPayload`:

Update the interface:
```typescript
interface TestConnectionSectionProps {
    getFormData: () => ModelFormData;
    getDirtyFields?: () => Partial<Record<string, boolean>>;
    isNew: boolean;
    modelAlias?: string;
    disabled?: boolean;
}
```

Update the component destructuring:
```typescript
export const TestConnectionSection = ({ getFormData, getDirtyFields, isNew, modelAlias, disabled }: TestConnectionSectionProps) => {
```

Update the `buildModelPayload` call inside `handleTestConnection`:
```typescript
const formData = getFormData();
const dirtyFields = getDirtyFields?.();
const payload = buildModelPayload(formData, dirtyFields);
```

Update the `useCallback` dependency array to include `getDirtyFields`:
```typescript
}, [getFormData, getDirtyFields, isNew, modelAlias]);
```

- [ ] **Step 3: Run tests**

Run: `cd client/webui/frontend && npx vitest --project=unit --run`

Expected: Existing tests may fail for PasswordInput since the component API changed. Other tests should pass.

- [ ] **Step 4: Commit**

```bash
git add client/webui/frontend/src/lib/components/models/ModelEditPage.tsx client/webui/frontend/src/lib/components/models/TestConnectionSection.tsx
git commit -m "refactor: thread dirtyFields through ModelEditPage and TestConnectionSection"
```

---

### Task 5: Rewrite PasswordInput tests

**Files:**
- Rewrite: `client/webui/frontend/src/stories/common/PasswordInput.test.tsx`

- [ ] **Step 1: Write new tests**

Replace the entire file with tests covering the new Controller-based component:

```tsx
/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { useForm, FormProvider } from "react-hook-form";
import { PasswordInput } from "../../lib/components/common/PasswordInput";

expect.extend(matchers);

// Wrapper that provides react-hook-form context for the Controller-based PasswordInput
const TestWrapper = ({
    hasStoredValue = false,
    disabled = false,
    placeholder,
    defaultValue = "",
}: {
    hasStoredValue?: boolean;
    disabled?: boolean;
    placeholder?: string;
    defaultValue?: string;
}) => {
    const methods = useForm({ defaultValues: { password: defaultValue } });
    return (
        <FormProvider {...methods}>
            <PasswordInput name="password" control={methods.control} hasStoredValue={hasStoredValue} disabled={disabled} placeholder={placeholder} />
        </FormProvider>
    );
};

describe("PasswordInput", () => {
    test("renders with password type by default", () => {
        render(<TestWrapper />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input).toHaveAttribute("type", "password");
    });

    test("toggles to text type when eye button is clicked", async () => {
        const user = userEvent.setup();
        render(<TestWrapper />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        const button = screen.getByRole("button");

        await user.click(button);
        expect(input).toHaveAttribute("type", "text");

        await user.click(button);
        expect(input).toHaveAttribute("type", "password");
    });

    test("shows stored value placeholder when hasStoredValue is true and field is empty", () => {
        render(<TestWrapper hasStoredValue />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input).toHaveAttribute("placeholder", "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022");
    });

    test("shows custom placeholder when hasStoredValue is false", () => {
        render(<TestWrapper placeholder="Enter API key" />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input).toHaveAttribute("placeholder", "Enter API key");
    });

    test("eye toggle is inert when hasStoredValue is true and field is empty", async () => {
        const user = userEvent.setup();
        render(<TestWrapper hasStoredValue />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        const button = screen.getByRole("button");

        // Click eye — should NOT toggle type since field is empty with stored value
        await user.click(button);
        expect(input).toHaveAttribute("type", "password");
    });

    test("eye toggle becomes functional after user types", async () => {
        const user = userEvent.setup();
        render(<TestWrapper hasStoredValue />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        const button = screen.getByRole("button");

        // Type something
        await user.click(input);
        await user.keyboard("my-secret");

        // Now eye should work
        await user.click(button);
        expect(input).toHaveAttribute("type", "text");
    });

    test("disables input and button when disabled prop is true", () => {
        render(<TestWrapper disabled />);
        const input = screen.getByRole("textbox");
        const button = screen.getByRole("button");
        expect(input).toBeDisabled();
        expect(button).toBeDisabled();
    });

    test("sets autocomplete to new-password", () => {
        render(<TestWrapper />);
        const input = screen.getByRole("textbox");
        expect(input).toHaveAttribute("autoComplete", "new-password");
    });

    test("eye button shows correct aria-label", async () => {
        const user = userEvent.setup();
        render(<TestWrapper />);
        const button = screen.getByRole("button");

        expect(button).toHaveAttribute("aria-label", "Show password");

        await user.click(button);
        expect(button).toHaveAttribute("aria-label", "Hide password");
    });

    test("renders with default value", () => {
        render(<TestWrapper defaultValue="existing-password" />);
        const input = screen.getByRole("textbox") as HTMLInputElement;
        expect(input.value).toBe("existing-password");
    });
});
```

- [ ] **Step 2: Run the tests**

Run: `cd client/webui/frontend && npx vitest --project=unit --run src/stories/common/PasswordInput.test.tsx`

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add client/webui/frontend/src/stories/common/PasswordInput.test.tsx
git commit -m "test: rewrite PasswordInput tests for Controller-based component with hasStoredValue"
```

---

### Task 6: Update PasswordInput stories

**Files:**
- Rewrite: `client/webui/frontend/src/stories/common/PasswordInput.stories.tsx`

- [ ] **Step 1: Write new stories**

Replace the entire file:

```tsx
import { useForm, FormProvider } from "react-hook-form";
import { PasswordInput } from "@/lib/components/common/PasswordInput";
import { FormFieldLayoutItem } from "@/lib/components/common";
import { expect, within } from "storybook/test";
import type { Meta, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/PasswordInput",
    parameters: {
        layout: "padded",
        docs: {
            description: {
                component:
                    "Controlled password input with show/hide toggle. Supports `hasStoredValue` to indicate a server-side credential exists. Eye toggle is always visible but inert when only the placeholder is shown.",
            },
        },
    },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

export const Basic: Story = {
    render: () => {
        const methods = useForm({ defaultValues: { password: "" } });
        return (
            <FormProvider {...methods}>
                <div className="max-w-md">
                    <FormFieldLayoutItem label="API Key" required>
                        <PasswordInput name="password" control={methods.control} placeholder="Enter API key" />
                    </FormFieldLayoutItem>
                </div>
            </FormProvider>
        );
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByPlaceholderText("Enter API key");

        await expect(input).toBeInTheDocument();
        await expect(input).toHaveAttribute("type", "password");

        const toggleButton = within(input.parentElement!).getByRole("button");
        await expect(toggleButton).toBeInTheDocument();
    },
};

export const WithStoredValue: Story = {
    render: () => {
        const methods = useForm({ defaultValues: { password: "" } });
        return (
            <FormProvider {...methods}>
                <div className="max-w-md">
                    <FormFieldLayoutItem label="API Key" required helpText="A credential is stored on the server. Type a new value to replace it.">
                        <PasswordInput name="password" control={methods.control} hasStoredValue />
                    </FormFieldLayoutItem>
                </div>
            </FormProvider>
        );
    },
};

export const WithHelpText: Story = {
    render: () => {
        const methods = useForm({ defaultValues: { password: "" } });
        return (
            <FormProvider {...methods}>
                <div className="max-w-md">
                    <FormFieldLayoutItem label="New Password" required helpText="Must be at least 8 characters">
                        <PasswordInput name="password" control={methods.control} placeholder="Enter new password" />
                    </FormFieldLayoutItem>
                </div>
            </FormProvider>
        );
    },
};

export const WithError: Story = {
    render: () => {
        const methods = useForm({ defaultValues: { password: "" } });
        return (
            <FormProvider {...methods}>
                <div className="max-w-md">
                    <FormFieldLayoutItem label="Password" required error={{ message: "Password is required" }}>
                        <PasswordInput name="password" control={methods.control} placeholder="Enter password" />
                    </FormFieldLayoutItem>
                </div>
            </FormProvider>
        );
    },
};

export const Disabled: Story = {
    render: () => {
        const methods = useForm({ defaultValues: { password: "" } });
        return (
            <FormProvider {...methods}>
                <div className="max-w-md">
                    <FormFieldLayoutItem label="Password" required>
                        <PasswordInput name="password" control={methods.control} placeholder="Enter password" disabled />
                    </FormFieldLayoutItem>
                </div>
            </FormProvider>
        );
    },
};
```

- [ ] **Step 2: Commit**

```bash
git add client/webui/frontend/src/stories/common/PasswordInput.stories.tsx
git commit -m "docs: update PasswordInput stories for new controlled component API"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run all unit tests**

Run: `cd client/webui/frontend && npx vitest --project=unit --run`

Expected: All tests pass.

- [ ] **Step 2: Run TypeScript type checking**

Run: `cd client/webui/frontend && npx tsc --noEmit`

Expected: No type errors.

- [ ] **Step 3: Verify no remaining references to removed constants**

Search for any remaining references to `REDACTED_CREDENTIAL_PLACEHOLDER` or `REDACTED_CREDENTIAL_FIELDS`:

Run: `grep -r "REDACTED_CREDENTIAL" client/webui/frontend/src/`

Expected: No matches.

- [ ] **Step 4: Commit (if any fixes were needed)**

Only commit if earlier steps revealed issues that required fixes.
