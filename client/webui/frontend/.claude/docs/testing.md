# Testing

## Framework

Vitest with two test projects configured in `vitest.config.ts`:

| Project     | Environment        | Use                         |
| ----------- | ------------------ | --------------------------- |
| `unit`      | jsdom              | Component and utility tests |
| `storybook` | Playwright browser | Storybook interaction tests |

## Commands

```sh
npm run test:unit              # run unit tests
npm run test:storybook         # run storybook tests
npm run ci:storybook:coverage  # both + coverage (CI mode)
```

## When to use which

**Unit tests** (`*.test.tsx`, jsdom) — logic, state, effects, and integrations:

- Hook behavior, provider interactions, API calls (mocked with MSW)
- Conditional rendering, edge cases, error states
- Form validation, callbacks, lifecycle effects
- Example: "send button is disabled when input is empty" (`src/stories/chat/ChatInputArea.test.tsx`)

**Storybook tests** (`*.stories.tsx` with `play` functions, real browser) — visual rendering and interaction:

- Component variants render correctly (Default, Destructive, Loading, etc.)
- Hover/click/keyboard triggers the right visual change
- Popovers, tooltips, and overlays appear on interaction
- Example: "hovering citation badge shows popover" (`src/stories/chat/Citation.stories.tsx`)

**Rule of thumb:** if you need to mock providers or assert on logic/state, write a unit test. If you need to verify how a component looks or behaves visually across variants, write a story with a `play` function.

## File conventions

- Name: `*.test.ts` or `*.test.tsx`
- Location: co-located next to the source file
- Example: `src/lib/utils/messageProcessing.test.ts`

## Writing a unit test

```ts
/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers); // required — enables toBeInTheDocument(), etc.

describe("MyComponent", () => {
    test("renders and responds to click", async () => {
        const user = userEvent.setup();
        const onClick = vi.fn();

        render(<MyComponent onClick={onClick} />);

        await user.click(screen.getByRole("button"));
        expect(onClick).toHaveBeenCalledOnce();
    });
});
```

## Mock providers

Use `StoryProvider` to wrap components that need context (auth, query client, theme, config, etc.):

```ts
import { StoryProvider } from "@/stories/mocks/StoryProvider";

render(
    <StoryProvider>
        <MyComponent />
    </StoryProvider>
);
```

`StoryProvider` accepts partial overrides for each context. See `src/stories/mocks/StoryProvider.tsx`.

Individual mock providers are also available in `src/stories/mocks/`:

- `MockAuthProvider` — authentication context
- `MockChatProvider` — chat context
- `MockConfigProvider` — config/feature flags
- `MockProjectProvider` — project context
- `MockTaskProvider` — task monitoring

## Setup files

- `.storybook/vitest.globals.ts` — localStorage mock, polyfills (loaded first)
- `.storybook/vitest.setup.ts` — matchMedia mock, ResizeObserver polyfill, Storybook annotations

## Mock data

Shared mock fixtures live in `src/stories/mocks/data.ts` and sibling files (e.g. `citations.ts`).
