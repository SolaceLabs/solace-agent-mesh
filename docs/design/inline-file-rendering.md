# Design Document: Inline File Rendering in Chat

**Author:** Expert Software Developer
**Date:** 2025-09-04
**Status:** Proposed

## 1. Objective

To enhance the user experience in the chat interface by rendering certain types of file attachments directly inline within the conversation flow, rather than just displaying a file badge. This allows users to view content like images, documents, and data files without needing to download them or open a separate preview panel.

## 2. Background

Currently, all file attachments sent by an agent are rendered as a simple badge showing the filename and providing a download link. While functional, this requires users to perform extra steps to view file contents. For common, easily renderable file types, displaying them directly in the chat stream would create a more fluid and intuitive interaction, similar to modern messaging applications.

The request is to support inline rendering for the following file types:
- **Images**: `png`, `jpg`, `gif`, etc.
- **Audio**: `mp3`, `wav`, etc.
- **Documents**: Markdown (rendered as HTML).
- **Data Files**: `csv`, `json`, `yaml`.

## 3. High-Level Design

The core of this feature will be implemented by enhancing the `FileAttachmentMessage` React component. This component will become responsible for determining if a file is renderable inline and managing the process of fetching and displaying its content.

The high-level workflow for each file attachment will be:

1.  **Check Renderability**: When `FileAttachmentMessage` receives a `fileAttachment` prop, it will use the existing `getRenderType` utility to check if the file's MIME type or extension corresponds to one of the supported inline types (image, audio, markdown, csv, json, yaml).
2.  **Check Content Source**: The component will check if the file content is provided directly as a base64 string (`file.content`) or if it needs to be fetched from a URI (`file.uri`).
3.  **Fetch Content (if needed)**: If the file is specified by a URI, the component will trigger an asynchronous fetch to a dedicated backend endpoint to retrieve the file content. During this fetch, a loading state will be displayed.
4.  **Render Content**: Once the content is available (either initially or after fetching), it will be passed to the existing `ContentRenderer` component, which already handles the logic for rendering different data types.
5.  **UI/UX**: The rendered content will be displayed within a styled container in the chat. A download button will be overlaid on the content, appearing on hover. For data-heavy files (CSV, JSON, YAML), the container will be scrollable.
6.  **Fallback**: If a file is not of a supported inline type, or if fetching/rendering fails, the component will gracefully fall back to displaying the standard `FileMessage` badge.

This approach maximizes code reuse by leveraging existing utilities (`getRenderType`) and components (`ContentRenderer`), ensuring a consistent look and feel with the side panel's file previewer.

## 4. Detailed Design

### 4.1. Component: `FileAttachmentMessage` (`client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`)

This will be the primary component for this feature.

**State Management:**
The component will be converted to a stateful component to manage:
- `isLoading: boolean`: Tracks the fetching of content from a URI.
- `error: string | null`: Stores any error message from the fetch operation.
- `fetchedContent: string | null`: Stores the base64 content fetched from a URI.

**Logic Flow:**
1.  On mount, `useMemo` will be used with `getRenderType` to determine if the file is a candidate for inline rendering.
2.  A `useEffect` hook will trigger if the file is renderable and has a `uri` but no `content`.
    - It will set `isLoading` to `true`.
    - It will call a new helper function, `fetchContentFromUri`, which will:
        - Parse the `artifact://` URI using the `parseArtifactUri` utility.
        - Construct the API endpoint: `/api/v1/artifacts/{filename}/versions/{version}`.
        - Use `authenticatedFetch` to get the file content as a blob.
        - Use `FileReader` to convert the blob to a base64 data URL.
        - On success, it will update the `fetchedContent` state and set `isLoading` to `false`.
        - On failure, it will set the `error` state and set `isLoading` to `false`.
3.  The `render` method will have conditional logic:
    - If `isLoading`, display a `<Spinner />` component inside a placeholder container.
    - If `error`, display a `<MessageBanner variant="error" />` with the error message.
    - If `contentToRender` (either `fileAttachment.content` or `fetchedContent`) is available:
        - The content will be decoded (if necessary) and passed to `<ContentRenderer />`.
        - The renderer will be wrapped in a `div` with `position: relative` and `group` class for the hover effect.
        - A `<Button>` with a `<Download />` icon will be positioned absolutely at the top-right, visible on `group-hover`.
        - For `csv`, `json`, `yaml`, and `markdown`, the container `div` will have `max-height: 400px` and `overflow-y: auto` to make it scrollable.
    - If none of the above, fall back to rendering the original `FileMessage` badge.

### 4.2. Utility: `parseArtifactUri` (`client/webui/frontend/src/lib/utils/download.ts`)

This utility function will be exported so it can be shared between the download hook and the new fetching logic in `FileAttachmentMessage`.

### 4.3. UI Components

-   **Container**: A `div` will wrap the `ContentRenderer`. It will have a border, rounded corners, and a max-width to fit within the chat bubble layout.
-   **Download Button**: A `<Button variant="ghost" size="icon">` will be used. It will be styled to have a semi-transparent background to be visible over various content types (e.g., images) and will only appear on hover.
-   **Loading/Error States**: The `<Spinner />` and `<MessageBanner />` components will be used for clear user feedback during asynchronous operations.

## 5. Affected Components

-   `client/webui/frontend/src/lib/components/chat/file/FileMessage.tsx`: Major changes to introduce state, fetching logic, and conditional rendering.
-   `client/webui/frontend/src/lib/utils/download.ts`: Minor change to export `parseArtifactUri`.
-   No other components should require direct modification, as the logic is well-encapsulated within `FileAttachmentMessage`.

## 6. Future Considerations

-   **Performance for Large Files**: For very large text-based files (e.g., multi-megabyte JSON), decoding and rendering could impact performance. We might consider virtualized rendering for these in the future.
-   **More File Types**: The `inlineRenderableTypes` array can be easily extended to support more file types (e.g., PDF.js for PDFs) as renderers become available.
-   **User Preference**: A user setting could be added to disable inline rendering for users who prefer the compact badge view.
