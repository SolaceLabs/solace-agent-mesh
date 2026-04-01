# PasswordInput Redesign: Dirty Tracking & Stored Value UX

**Date:** 2026-03-31
**Scope:** Models UI only (PasswordInput + ModelEdit)
**Status:** Draft

## Problem

The current password field editing flow uses `"<encrypted>"` as a sentinel value placed into form fields to represent stored server-side credentials. This has several issues:

1. The eye toggle reveals `"<encrypted>"` — useless to the user
2. A sentinel string flowing through the form as a real value is fragile (must be stripped before submission)
3. No clear distinction between "user hasn't touched this" and "user intentionally cleared it"
4. Inconsistent with the desired UX pattern: asterisk placeholder indicating a stored value exists

## Design Decisions

### Agreed

- **Asterisk placeholder:** Credential fields during edit show `"••••••••"` as an HTML placeholder (not a form value) to indicate a stored credential exists server-side
- **Eye toggle always visible:** Signals "this is a sensitive field" even when no user input is present (Jamie's point — consistent with patterns like Gmail)
- **Eye toggle inert on placeholder:** When only the placeholder is shown (no user input), the eye is visible but does not toggle the input type
- **Eye toggle functional on user input:** Once the user types, the eye toggles between visible text and masked input as normal
- **Dirty tracking via react-hook-form `dirtyFields`:** No custom hook. RHF's built-in `formState.dirtyFields` determines whether a credential field was modified
- **Omit unchanged credentials from payload:** `buildModelPayload` checks `dirtyFields` and excludes credential fields the user didn't touch, rather than sending empty strings
- **No `"<encrypted>"` sentinel:** `REDACTED_CREDENTIAL_PLACEHOLDER` and `REDACTED_CREDENTIAL_FIELDS` are removed entirely
- **No backend changes:** The existing merge logic in model_config_service.py already supports partial auth_config updates. Test connection endpoint also falls back to stored credentials when fields are omitted.

### Open

- **Clear behavior:** What happens when a user clears a credential field during edit (backspaces everything). Options discussed: revert to placeholder (safest), allow empty, or confirm. Deferred — for now, natural HTML behavior (field stays empty). To be revisited.

## Component Design

### PasswordInput (presentational component)

**Props:**

```typescript
interface PasswordInputProps {
  name: string;
  control: Control<any>;
  hasStoredValue?: boolean;   // true = show asterisk placeholder, eye inert when empty
  placeholder?: string;
  disabled?: boolean;
  rules?: object;             // RHF validation rules
}
```

**Internal state:** `showPassword` (boolean) — managed internally, not by parent.

**Behavior matrix:**

| State | Field value | Placeholder shown | Eye visible | Eye functional |
|-------|-------------|-------------------|-------------|----------------|
| New (no stored value) | empty | normal placeholder text | Yes | Yes |
| Edit (stored, untouched) | empty | `"••••••••"` | Yes | No (inert) |
| Edit (user typing) | user input | none | Yes | Yes |
| Edit (user cleared) | empty | TBD (open decision) | Yes | TBD |

**Key changes from current:**
- Switches from `register` (uncontrolled) to `Controller` (controlled) — consistent with Select, ComboBox fields in the same form
- Manages its own show/hide toggle state internally
- `hasStoredValue` drives the asterisk placeholder instead of a sentinel form value
- Eye toggle rendered via the same Button+Icon pattern, but `onClick` is a no-op when `hasStoredValue && value is empty`

### ModelEdit Integration

- Remove `showPassword` state map (`useState<Record<string, boolean>>({})`) — no longer needed
- When populating credentials during edit, set field defaults to `""` (not `REDACTED_CREDENTIAL_PLACEHOLDER`)
- Track which credential fields have stored values based on the backend response (`authConfig` keys present for the model being edited)
- Pass `hasStoredValue` per-field (true only if the backend returned a value for that specific credential field, not just `!isNew`)
- Pass `control` instead of `register` for password fields in `renderField`
- Pass `dirtyFields` to `buildModelPayload` on submit

### modelProviderUtils.ts

- Update `buildModelPayload` signature to accept `dirtyFields: Record<string, boolean>`
- For each credential field: only include in the `authConfig` payload if `dirtyFields[fieldName]` is true
- Remove `REDACTED_CREDENTIAL_PLACEHOLDER` constant
- Remove `REDACTED_CREDENTIAL_FIELDS` constant
- Remove the placeholder stripping loop in `buildModelPayload`
- Keep `AUTH_CONFIG_TO_FORM_FIELD_MAP` — still needed to determine which fields have stored values during edit

## Backend Compatibility

**No backend changes required.**

- **Save (PUT):** Backend merges `request.auth_config` with existing config. Omitted keys are preserved from stored config. This is the intended partial-update behavior.
- **Test connection (POST /models/test):** Endpoint accepts an alias for existing models and uses stored credentials as fallback for any missing auth_config fields.
- **Create (POST):** All credential fields are required and present — no change in behavior.

## Files Changed

| File | Change |
|------|--------|
| `PasswordInput.tsx` | Rewrite: register → Controller, add hasStoredValue, internal showPassword, asterisk placeholder, conditional eye behavior |
| `ModelEdit.tsx` | Remove showPassword state, set credential defaults to "", pass hasStoredValue + control, pass dirtyFields to payload builder |
| `modelProviderUtils.ts` | Update buildModelPayload for dirtyFields, remove REDACTED_CREDENTIAL_PLACEHOLDER, REDACTED_CREDENTIAL_FIELDS, stripping logic |
| `PasswordInput.test.tsx` | Update tests for new props (FormProvider wrapper, hasStoredValue states, eye toggle behavior) |
| `PasswordInput.stories.tsx` | Update stories for new API |

## Not Changing

- Backend API endpoints or services
- Test connection flow (already supports credential fallback)
- PasswordInput barrel export
- Other consumers (gateways/connectors — future scope)
