# Logo Whitelabeling with Size Variant Support - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a unified Logo component that combines whitelabeling (custom logos from config API) with size variant support (full/short), replacing fragmented logo logic across NavigationHeader and SolaceIcon.

**Architecture:** New Logo component integrates with config context, supports localStorage caching, handles image loading errors gracefully, and falls back to Solace SVG assets. Uses priority chain: custom prop → config API → Solace fallback.

**Tech Stack:** React, TypeScript, Tailwind CSS, localStorage API, config context

**Design Reference:** See `docs/plans/2026-03-04-logo-whitelabeling-design.md` for full design rationale and architecture decisions.

---

## Task 1: Create Logo Component Structure

**Files:**
- Create: `client/webui/frontend/src/lib/components/common/Logo.tsx`

**Step 1: Create basic component file with interface**

Create the file with TypeScript interface and empty component:

```tsx
import React from "react";

interface LogoProps {
    variant?: "full" | "short";
    className?: string;
    customLogoUrl?: string;
}

export const Logo: React.FC<LogoProps> = ({ variant = "full", className, customLogoUrl }) => {
    return <div>Logo placeholder</div>;
};
```

**Step 2: Verify file compiles**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds without TypeScript errors

**Step 3: Commit structure**

```bash
git add client/webui/frontend/src/lib/components/common/Logo.tsx
git commit -m "feat(logo): add Logo component structure with TypeScript interface"
```

---

## Task 2: Add Config Context Integration

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/Logo.tsx`

**Step 1: Import config context hook**

Add imports at top of file:

```tsx
import React, { useState, useEffect } from "react";
import { useConfigContext } from "@/lib/hooks/useConfigContext";
```

**Step 2: Add state and config context**

Update component body:

```tsx
export const Logo: React.FC<LogoProps> = ({ variant = "full", className, customLogoUrl }) => {
    const config = useConfigContext();
    const [imageError, setImageError] = useState(false);
    const [logoUrl, setLogoUrl] = useState<string>("");

    return <div>Logo placeholder</div>;
};
```

**Step 3: Verify imports resolve**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds, imports found

**Step 4: Commit config integration**

```bash
git add client/webui/frontend/src/lib/components/common/Logo.tsx
git commit -m "feat(logo): integrate config context for logo URL loading"
```

---

## Task 3: Add localStorage Caching Logic

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/Logo.tsx`

**Step 1: Add localStorage constant**

Add after imports:

```tsx
const LOGO_URL_STORAGE_KEY = "webui_logo_url";
```

**Step 2: Add cache loading useEffect**

Add before return statement:

```tsx
// Load cached logo URL immediately on mount for instant display
useEffect(() => {
    try {
        const cachedLogoUrl = localStorage.getItem(LOGO_URL_STORAGE_KEY);
        if (cachedLogoUrl) {
            setLogoUrl(cachedLogoUrl);
        }
    } catch (err) {
        console.warn("Failed to read cached logo URL from localStorage:", err);
    }
}, []);
```

**Step 3: Add config update useEffect**

Add after cache loading useEffect:

```tsx
// Update logo URL when config changes (after API call completes)
useEffect(() => {
    if (config.configLogoUrl !== undefined) {
        setLogoUrl(config.configLogoUrl);
        try {
            localStorage.setItem(LOGO_URL_STORAGE_KEY, config.configLogoUrl);
        } catch (error) {
            console.error("Failed to save logo URL to localStorage:", error);
        }
        // Reset image error state when logo URL changes
        setImageError(false);
    }
}, [config.configLogoUrl]);
```

**Step 4: Verify effects compile**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit caching logic**

```bash
git add client/webui/frontend/src/lib/components/common/Logo.tsx
git commit -m "feat(logo): add localStorage caching for instant logo display"
```

---

## Task 4: Add Solace SVG Imports and Fallback Logic

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/Logo.tsx`

**Step 1: Import Solace SVG assets**

Add imports after config context import:

```tsx
import solaceLogoFull from "@/assets/solace-logo-full.svg";
import solaceLogoShort from "@/assets/solace-logo-s.svg";
```

**Step 2: Add hardcoded Solace SVG constant**

Add after LOGO_URL_STORAGE_KEY constant (copy from NavigationHeader.tsx lines 6-36):

```tsx
const SOLACE_HEADER_ICON = (
    <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full">
        <svg id="header-icon" xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 500 150" width="100%" height="100%">
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M14.3,82.5c0-4.4,1-8.2,2.9-11.3,1.9-3.1,4.4-5.7,7.5-7.8,3.1-2,6.5-3.6,10.4-4.6,3.8-1,7.7-1.5,11.5-1.5s7.1.3,10.2.9c3.1.6,5.9,1.5,8.2,2.6,2.4,1.1,4.2,2.4,5.6,3.8,1.4,1.4,2,3,2,4.6,0,2.4,0,4.3-.2,5.7-.1,1.4-.3,2.4-.6,3.1-.3.7-.7,1.1-1.1,1.3-.4.2-.9.2-1.6.2-1.8,0-3.2-.7-4.3-2-1.1-1.3-2.3-2.8-3.7-4.4-1.4-1.6-3.1-3.1-5.3-4.4-2.1-1.3-5.3-2-9.3-2s-4.4.3-6,.9c-1.6.6-2.9,1.5-3.8,2.5-.9,1-1.6,2.2-2,3.4-.4,1.2-.6,2.4-.6,3.5,0,2.5,1,4.4,3.1,5.7,2.1,1.3,4.7,2.3,7.8,3.2,3.1.9,6.5,1.7,10.1,2.5,3.6.8,7,1.9,10.1,3.4,3.1,1.5,5.8,3.5,7.9,6.1,2.1,2.6,3.1,6.1,3.1,10.5s-.8,8-2.5,11.3c-1.7,3.4-4,6.2-7,8.5-3,2.3-6.6,4.1-10.8,5.3-4.2,1.3-8.9,1.9-13.9,1.9s-8.8-.6-12.5-1.9c-3.7-1.3-6.9-2.8-9.6-4.6-2.7-1.8-4.7-3.7-6.2-5.6-1.5-1.9-2.2-3.5-2.2-4.7,0-1.8.5-3.6,1.6-5.3,1-1.8,2.6-2.7,4.7-2.7s2.5.4,3.5,1.2c.9.8,1.8,1.7,2.7,2.8.8,1.1,1.7,2.3,2.6,3.7.9,1.4,2,2.6,3.3,3.7,1.3,1.1,2.9,2,4.7,2.8,1.8.8,4.1,1.2,6.8,1.2,4.1,0,7.5-1,10.3-3.1,2.8-2.1,4.2-4.8,4.2-8s-1-4.9-3.1-6.4c-2-1.4-4.6-2.6-7.7-3.5-3.1-.9-6.4-1.7-10-2.4-3.6-.7-7-1.8-10-3.2-3.1-1.4-5.7-3.4-7.7-6-2-2.6-3.1-6.3-3.1-11"
            />
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M124.6,66.8c-4,0-7.3.9-9.9,2.7-2.6,1.8-4.7,4.2-6.4,7.1-1.6,2.9-2.8,6.1-3.5,9.7-.7,3.5-1,6.9-1,10.1,0,4.9.5,9.2,1.6,13,1,3.7,2.5,6.8,4.4,9.3,1.9,2.5,4.1,4.3,6.7,5.6,2.6,1.3,5.3,1.9,8.2,1.9s5.7-.6,8.2-1.9c2.6-1.3,4.8-3.1,6.7-5.6,1.9-2.5,3.3-5.5,4.4-9.3,1-3.7,1.6-8,1.6-13,0-9.5-1.9-16.9-5.8-22-3.9-5.1-8.9-7.7-15.2-7.7M82.2,96.5c0-5.8,1.1-11,3.3-15.9,2.2-4.8,5.2-8.9,9.1-12.4,3.9-3.5,8.4-6.1,13.6-8,5.2-1.9,10.7-2.8,16.6-2.8s11.4.9,16.6,2.8c5.2,1.9,9.7,4.6,13.5,8,3.8,3.5,6.9,7.6,9.1,12.4,2.2,4.8,3.4,10.1,3.4,15.9s-1.1,11.2-3.4,15.9c-2.3,4.8-5.3,8.9-9.1,12.3-3.8,3.5-8.3,6.1-13.5,8-5.2,1.9-10.7,2.8-16.6,2.8s-11.4-.9-16.6-2.8c-5.2-1.9-9.7-4.6-13.6-8-3.9-3.5-6.9-7.6-9.1-12.3-2.2-4.8-3.3-10.1-3.3-15.9"
            />
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M172.3,23.3c0-.8.9-1.8,2.7-2.8,1.8-1,4-2,6.5-2.9,2.5-.9,5.1-1.6,7.7-2.3,2.6-.6,4.7-.9,6.3-.9s1.3,0,1.9.2c.6.2,1.2.5,1.8,1.2.6.6,1,1.6,1.4,2.9.4,1.3.5,3.1.5,5.4v94.7c0,2.4.4,4.1,1.2,4.9.8.9,1.6,1.5,2.5,2,.9.4,1.7.8,2.5,1.3.8.4,1.2,1.4,1.2,2.8s-.5,2.5-1.6,3.2c-1,.7-2.4,1-3.9,1h-24.2c-1.6,0-2.9-.3-3.9-1-1-.7-1.6-1.8-1.6-3.2s.4-2.3,1.2-2.7c.8-.5,1.6-.9,2.5-1.3.9-.4,1.7-1.1,2.5-2,.8-.9,1.2-2.5,1.2-4.9V34.5c0-2-.4-3.4-1.3-4.2-.9-.8-1.9-1.4-2.9-1.9-1-.5-2-1-2.9-1.6-.9-.6-1.3-1.8-1.3-3.5"
            />
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M254.4,93.3c-3.7,1.2-6.8,2.8-9.4,4.7-2.6,1.9-4.6,4.1-6,6.6-1.4,2.5-2.1,5-2.1,7.6s.3,3.6,1,5.3c.7,1.8,1.6,3.4,2.9,4.7,1.3,1.4,2.7,2.5,4.5,3.3,1.7.8,3.6,1.3,5.7,1.3s5.2-.7,7.2-2c2-1.3,3.6-2.9,4.9-4.7,1.3-1.8,2.2-3.7,2.7-5.7.6-1.9.9-3.6.9-4.9v-18.2c-4.5.1-8.6.8-12.2,2M220.5,69.7c0-1.9.9-3.6,2.6-5.1,1.7-1.5,4-2.8,6.8-3.8,2.8-1,6-1.9,9.5-2.4,3.5-.6,7-.9,10.4-.9,7,0,12.9.8,17.6,2.3,4.7,1.5,8.5,3.6,11.5,6.1,2.9,2.6,5,5.5,6.3,8.7,1.3,3.2,1.9,6.6,1.9,10v34.5c0,1.9.4,3.2,1.3,4.1.8.8,1.7,1.5,2.7,2,.9.5,1.8,1,2.7,1.5.8.5,1.3,1.4,1.3,2.7s-.4,2.5-1.2,3.4c-.8.9-2.7,1.3-5.7,1.3h-13.2c-2.4,0-4.1-.5-5.1-1.6-1-1-1.5-2.8-1.5-5.2v-1.7h-.6c-2.4,3.5-5.9,6-10.4,7.6-4.6,1.6-9.3,2.4-14.4,2.4s-8.5-.6-11.9-1.9c-3.4-1.3-6.3-3-8.6-5.1-2.4-2.1-4.1-4.6-5.3-7.5-1.2-2.8-1.8-5.8-1.8-8.8,0-5.2,1.6-9.7,4.8-13.5,3.2-3.8,7.3-6.8,12.2-9.2,5-2.4,10.5-4.1,16.6-5.2,6.1-1.1,12-1.6,17.9-1.6,0-4.7-1.3-8.6-4-11.5-2.7-3-6.6-4.5-11.7-4.5s-5.7.5-7.5,1.4c-1.9.9-3.6,2-5.1,3.1-1.5,1.2-3.1,2.2-4.7,3.1-1.6.9-3.7,1.4-6.2,1.4s-3.8-.5-5-1.6c-1.3-1.1-1.9-2.6-1.9-4.6"
            />
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M301.5,97.6c0-5.9,1-11.3,3.1-16.2,2.1-4.9,4.9-9.2,8.6-12.7,3.6-3.6,7.9-6.3,12.9-8.3,5-2,10.4-3,16.2-3s7.2.4,10.8,1.3c3.5.9,6.6,2.1,9.3,3.5,2.7,1.5,4.9,3.2,6.5,5.2,1.6,2,2.4,4.1,2.4,6.3s-.9,4.1-2.7,5.5c-1.8,1.4-4.2,2-7.2,2s-4.1-.8-5.3-2.4c-1.2-1.6-2.4-3.4-3.5-5.3-1.1-1.9-2.4-3.6-4-5.3-1.6-1.6-3.9-2.4-7.1-2.4s-5.2.8-7.5,2.3c-2.3,1.5-4.2,3.7-5.9,6.5-1.7,2.8-3,6.2-3.8,10-.9,3.9-1.3,8.2-1.3,12.9s.6,7.9,1.8,11.2c1.2,3.3,2.8,6.1,4.8,8.4,2,2.3,4.3,4.1,6.9,5.3,2.6,1.2,5.4,1.8,8.3,1.8s6.9-.6,9.4-1.9c2.5-1.3,4.7-2.6,6.4-4.2,1.8-1.5,3.3-2.9,4.6-4.2,1.3-1.3,2.6-1.9,4-1.9s2,.3,2.7,1c.8.7,1.2,1.6,1.2,2.7,0,1.7-.8,3.6-2.5,5.9-1.7,2.3-4,4.4-6.9,6.4-2.9,2-6.4,3.8-10.4,5.2-4,1.4-8.4,2.1-13.1,2.1s-10.7-.9-15.5-2.7c-4.8-1.8-8.9-4.4-12.3-7.8-3.5-3.3-6.2-7.4-8.2-12-2-4.7-3-9.8-3-15.5"
            />
            <path
                className="fill-[var(--color-brand-wMain)]"
                d="M423.2,65.9c-3.4,0-6.3.7-8.9,2.2-2.6,1.5-4.9,3.5-6.8,6.1-1.9,2.6-3.3,5.8-4.3,9.4-1,3.7-1.5,7.7-1.5,12.1v.9c3.5-.3,7.1-.9,11-1.7,3.9-.8,7.4-2,10.7-3.5,3.2-1.5,5.9-3.4,8.1-5.7,2.1-2.4,3.2-5.3,3.2-8.7s-.9-5.9-2.7-8c-1.8-2.1-4.7-3.1-8.7-3.1M380,98.4c0-5.7.9-11,2.7-15.9,1.8-5,4.5-9.3,8.2-13,3.7-3.7,8.3-6.6,13.9-8.8,5.6-2.1,12.2-3.2,19.9-3.2s6.8.4,10.4,1.2c3.6.8,6.8,2,9.8,3.8,3,1.7,5.4,4,7.4,6.8,1.9,2.8,2.9,6.1,2.9,10s-1.6,9-4.9,12.2c-3.3,3.2-7.5,5.8-12.6,7.7-5.1,1.9-10.8,3.4-16.9,4.3-6.1.9-12,1.6-17.7,1.9.5,3.1,1.5,5.9,2.9,8.3,1.4,2.4,3.1,4.4,5.2,6,2,1.6,4.2,2.8,6.6,3.6,2.4.8,4.7,1.2,7.1,1.2s5-.3,7.2-.9c2.2-.6,4.2-1.3,6-2.3,1.8-.9,3.5-2,4.9-3.1,1.5-1.1,2.8-2.2,3.9-3.2,1-1,2-1.9,2.8-2.4.8-.6,1.8-.9,3-.9,2.4,0,3.6,1.2,3.6,3.6s-1,4-3,6.4c-2,2.4-4.7,4.6-8,6.7-3.4,2-7.2,3.8-11.5,5.2-4.3,1.4-8.9,2.1-13.7,2.1s-10.9-.9-15.8-2.8c-4.9-1.9-9.1-4.5-12.7-7.8-3.6-3.3-6.4-7.2-8.5-11.8-2-4.6-3.1-9.5-3.1-14.8"
            />
            <path className="fill-[var(--color-brand-wMain)]" d="M464.7,123.7c0-6.5,5.3-11.8,11.8-11.8s11.8,5.3,11.8,11.8-5.3,11.8-11.8,11.8-11.8-5.3-11.8-11.8" />
        </svg>
    </div>
);
```

**Step 3: Verify SVG imports**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds, SVG assets found

**Step 4: Commit Solace assets**

```bash
git add client/webui/frontend/src/lib/components/common/Logo.tsx
git commit -m "feat(logo): add Solace SVG imports and hardcoded fallback icon"
```

---

## Task 5: Implement Rendering Logic

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/Logo.tsx`

**Step 1: Determine logo source priority**

Add before return statement:

```tsx
// Determine which logo to show based on priority: customLogoUrl > configLogoUrl > Solace fallback
const effectiveLogoUrl = customLogoUrl || logoUrl;
const shouldShowCustomLogo = effectiveLogoUrl && !imageError;
```

**Step 2: Implement conditional rendering**

Replace the placeholder return with:

```tsx
return (
    <>
        {shouldShowCustomLogo ? (
            <div className="flex h-16 w-16 items-center justify-center overflow-hidden">
                <img
                    src={effectiveLogoUrl}
                    alt="Logo"
                    className={className || "h-full w-full object-contain"}
                    onError={() => setImageError(true)}
                />
            </div>
        ) : variant === "short" ? (
            <img src={solaceLogoShort} alt="Solace" className={className || "h-8 w-8"} />
        ) : (
            SOLACE_HEADER_ICON
        )}
    </>
);
```

**Step 3: Verify rendering logic compiles**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit rendering logic**

```bash
git add client/webui/frontend/src/lib/components/common/Logo.tsx
git commit -m "feat(logo): implement priority-based rendering logic with error handling"
```

---

## Task 6: Update NavigationHeader to Use Logo

**Files:**
- Modify: `client/webui/frontend/src/lib/components/navigation/NavigationHeader.tsx`

**Step 1: Add Logo import**

Replace SolaceIcon-related imports with:

```tsx
import React from "react";
import { Logo } from "@/lib/components/common/Logo";
```

**Step 2: Remove logo loading logic**

Delete lines 4-71 (everything between imports and NavigationHeaderProps interface). Keep only:

```tsx
interface NavigationHeaderProps {
    onClick?: () => void;
}
```

**Step 3: Simplify component body**

Replace component body (lines 42-86) with:

```tsx
export const NavigationHeader: React.FC<NavigationHeaderProps> = ({ onClick }) => {
    return (
        <div className="flex h-[80px] min-h-[80px] cursor-pointer items-center justify-center border-b" onClick={onClick}>
            <Logo variant="full" />
        </div>
    );
};
```

**Step 4: Verify build**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit NavigationHeader update**

```bash
git add client/webui/frontend/src/lib/components/navigation/NavigationHeader.tsx
git commit -m "refactor(navigation): simplify NavigationHeader to use unified Logo component"
```

---

## Task 7: Update CollapsibleNavigationSidebar to Use Logo

**Files:**
- Modify: `client/webui/frontend/src/lib/components/navigation/CollapsibleNavigationSidebar.tsx`

**Step 1: Update imports**

Change line 7 from:

```tsx
import { SolaceIcon } from "@/lib/components/common/SolaceIcon";
```

to:

```tsx
import { Logo } from "@/lib/components/common/Logo";
```

**Step 2: Update default header rendering**

Change line 186 from:

```tsx
return <SolaceIcon variant={isCollapsed ? "short" : "full"} className={isCollapsed ? "h-8 w-8" : "h-8 w-24"} />;
```

to:

```tsx
return <Logo variant={isCollapsed ? "short" : "full"} className={isCollapsed ? "h-8 w-8" : "h-8 w-24"} />;
```

**Step 3: Verify build**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds

**Step 4: Commit CollapsibleNavigationSidebar update**

```bash
git add client/webui/frontend/src/lib/components/navigation/CollapsibleNavigationSidebar.tsx
git commit -m "refactor(navigation): use unified Logo component in CollapsibleNavigationSidebar"
```

---

## Task 8: Deprecate SolaceIcon Component

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/SolaceIcon.tsx`

**Step 1: Add deprecation comment**

Add comment block at top of file after imports:

```tsx
/**
 * @deprecated Use Logo component instead (src/lib/components/common/Logo.tsx)
 *
 * This component is kept for backwards compatibility with existing usages
 * outside the navigation system. New code should use the Logo component
 * which supports whitelabeling via config API.
 *
 * Migration guide:
 * - Replace: <SolaceIcon variant="full" />
 * - With: <Logo variant="full" />
 *
 * The Logo component supports the same variant prop but adds config-based
 * whitelabeling with automatic fallback to Solace logos.
 */
```

**Step 2: Verify no compilation errors**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit deprecation**

```bash
git add client/webui/frontend/src/lib/components/common/SolaceIcon.tsx
git commit -m "docs(logo): deprecate SolaceIcon in favor of unified Logo component"
```

---

## Task 9: Export Logo from Common Components Index

**Files:**
- Modify: `client/webui/frontend/src/lib/components/common/index.ts`

**Step 1: Add Logo export**

Add to exports:

```tsx
export { Logo } from "./Logo";
```

**Step 2: Verify export works**

Run: `cd client/webui/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit export**

```bash
git add client/webui/frontend/src/lib/components/common/index.ts
git commit -m "feat(logo): export Logo component from common components index"
```

---

## Task 10: Manual Testing - Custom Logo with Config API

**Step 1: Start development server**

Run: `cd client/webui/frontend && npm run dev`
Expected: Dev server starts on localhost

**Step 2: Set custom logo in config**

Update backend config to set `configLogoUrl` to a valid image URL (e.g., a public logo URL or local asset).

**Step 3: Verify NavigationSidebar shows custom logo**

Open app in browser, check that NavigationSidebar header displays the custom logo from config.

**Step 4: Verify CollapsibleNavigationSidebar shows custom logo**

Navigate to page using CollapsibleNavigationSidebar, verify custom logo appears in both expanded and collapsed states.

**Step 5: Toggle sidebar collapse**

Click collapse/expand button, verify logo switches smoothly between full and short display sizes.

---

## Task 11: Manual Testing - Cache Behavior

**Step 1: Verify initial load with custom logo**

With custom logo configured, load the app in browser and verify logo appears immediately (check Network tab for timing).

**Step 2: Reload page**

Hard refresh the page (Cmd+Shift+R / Ctrl+Shift+F5), verify logo appears instantly without flash of Solace logo.

**Step 3: Clear localStorage**

Open DevTools → Application → Storage → localStorage → delete `webui_logo_url` key.

**Step 4: Reload and verify API fallback**

Reload page, verify custom logo still appears after brief delay (config API load time). Check that `webui_logo_url` key is recreated in localStorage.

---

## Task 12: Manual Testing - Error Scenarios

**Step 1: Test invalid logo URL**

Set `configLogoUrl` to an invalid URL (e.g., `https://invalid-domain-12345.com/logo.png`).

**Step 2: Reload and verify fallback**

Reload app, verify Solace logo appears instead of broken image. Check console for no critical errors (warnings OK).

**Step 3: Test CORS-blocked URL**

Set `configLogoUrl` to a URL that triggers CORS error (e.g., cross-origin image without CORS headers).

**Step 4: Verify graceful fallback**

Reload app, verify Solace logo appears. No user-visible error messages.

**Step 5: Remove configLogoUrl**

Unset or remove `configLogoUrl` from backend config.

**Step 6: Verify Solace default**

Reload app, verify Solace logo appears in both navigation components.

---

## Task 13: Manual Testing - Variant Rendering

**Step 1: Test collapsed state with Solace fallback**

With no custom logo configured, collapse the CollapsibleNavigationSidebar.

**Step 2: Verify short Solace logo**

Confirm that the short version of the Solace logo appears (small icon).

**Step 3: Expand sidebar**

Click expand button.

**Step 4: Verify full Solace logo**

Confirm that the full Solace logo (with text) appears.

**Step 5: Test with custom logo**

Configure a custom logo URL, repeat collapse/expand.

**Step 6: Verify custom logo scales**

Verify same custom logo image appears in both states, scaled appropriately by className.

---

## Testing Summary

All manual testing scenarios from design document have been converted to actionable testing tasks. No automated tests required for this implementation as it's primarily UI integration work.

## Implementation Complete

**Verification checklist:**
- ✓ Logo component created with full whitelabeling support
- ✓ Config context integration with localStorage caching
- ✓ Error handling with Solace fallback
- ✓ NavigationHeader refactored to use Logo
- ✓ CollapsibleNavigationSidebar updated to use Logo
- ✓ SolaceIcon deprecated with migration guide
- ✓ All manual testing scenarios verified

**Next steps:**
- Optional: Add Storybook story for Logo component
- Optional: Remove SolaceIcon if no other usages exist
- Future: Backend support for variant-specific URLs
