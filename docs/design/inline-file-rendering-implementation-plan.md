# Implementation Plan: Inline File Rendering in Chat

**Author:** Expert Software Developer
**Date:** 2025-09-04
**Status:** In Progress

This document outlines the step-by-step plan to implement inline rendering for file attachments in the chat interface, based on the approved design document.

---

### 1. Project Setup & Utilities

1.  **Export `parseArtifactUri` Utility**:
    -   **File**: `client/webui/frontend/src/lib/utils/download.ts`
    -   **Action**: Add the `export` keyword to the `parseArtifactUri` function declaration. This makes it accessible to other components, specifically `FileAttachmentMessage`, which will need it to handle `artifact://` URIs.

### 2. `FileAttachmentMessage` Component Refactoring

The majority of the work will be done in `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`.

2.  **Convert to a Stateful Component**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**: Refactor the `FileAttachmentMessage` component to use React hooks (`useState`, `useEffect`, `useMemo`).

3.  **Add State Variables**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**: Introduce the following state variables using `useState`:
        -   `isLoading: boolean`: To track the loading state while fetching content from a URI. Initialize to `false`.
        -   `error: string | null`: To store any error messages that occur during fetching. Initialize to `null`.
        -   `fetchedContent: string | null`: To store the base64-encoded file content fetched from a URI. Initialize to `null`.
        -   `renderError: string | null`: To capture errors from the `ContentRenderer` itself.

4.  **Determine File Renderability**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**:
        -   Use the `useMemo` hook to call `getRenderType(fileAttachment.name, fileAttachment.mime_type)`. This will determine if the file is of a type we can render inline.
        -   Define a constant array `inlineRenderableTypes` containing `["image", "audio", "markdown", "csv", "json", "yaml"]` to check against the result.

5.  **Implement Asynchronous Content Fetching**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**:
        -   Create a `useEffect` hook that depends on `fileAttachment.uri`, `fileAttachment.content`, and the memoized `renderType`.
        -   Inside the effect, add a condition to proceed only if the file is renderable, has a `uri`, and does not already have `content`.
        -   Set `isLoading` to `true` and clear any previous `error`.
        -   Use a `try...catch` block for the fetch logic.
        -   **Inside `try`**:
            -   Call the `parseArtifactUri` utility to get the filename and version.
            -   Construct the API URL: `/api/v1/artifacts/{filename}/versions/{version}`.
            -   Use `authenticatedFetch` to request the file content.
            -   If the response is not `ok`, throw an error.
            -   Convert the response `blob()` to a base64 string using `FileReader`.
            -   On successful read, call `setFetchedContent` with the base64 data.
        -   **Inside `catch`**: Log the error and call `setError` with an appropriate message.
        -   **Inside `finally`**: Set `isLoading` to `false`.

6.  **Implement Conditional Rendering Logic**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**: Structure the component's return statement with the following logic:
        -   **Embedded Check**: If `isEmbedded` is true, immediately return the standard `<FileMessage />` badge to avoid rendering large content inline from data URIs in text.
        -   **Renderable Check**: If the `renderType` is in `inlineRenderableTypes`:
            -   If `isLoading`, return a container with a `<Spinner />`.
            -   If `error`, return a `<MessageBanner variant="error" />` with the error message.
            -   If `contentToRender` (from `fetchedContent` or `fileAttachment.content`) is available:
                -   Create a `div` with `relative group` classes to act as the main container.
                -   Create a `div` for the `ContentRenderer` and apply a `max-height` and `overflow-y: auto` style for scrollable types (CSV, JSON, YAML, Markdown).
                -   Render the `<ContentRenderer />`, passing the content, type, and `setRenderError` callback.
                -   Add a `<Button>` with a `<Download />` icon. Position it absolutely in the top-right corner and make it visible on `group-hover`.
        -   **Fallback**: If none of the above conditions are met, return the default `<FileMessage />` badge. This handles non-renderable types and cases where content is missing.

### 3. Final Review

7.  **Code Review and Cleanup**:
    -   **File**: `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`
    -   **Action**: Review the component to ensure all logical paths are handled, props are correctly passed, and the code is clean and readable.
    -   **File**: `client/webui/frontend/src/lib/utils/download.ts`
    -   **Action**: Double-check that `parseArtifactUri` is correctly exported.
