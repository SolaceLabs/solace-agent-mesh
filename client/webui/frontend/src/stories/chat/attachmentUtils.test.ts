/**
 * Tests for shared attachment helpers. Pins extension/mime fixtures so
 * future edits cannot silently change what counts as an image/text/doc
 * — the PPTX/DOCX-vs-"xml" trap is guarded by caller-side ordering
 * (`!isDoc && !isImage && supportsTextPreview(...)`), so the fixtures
 * below are the canary: `supportsTextPreview` DOES return true for
 * Office XML mimes, and the caller must not rely on it to reject them.
 */
import { describe, test, expect } from "vitest";

import { MAX_THUMBNAIL_FILE_BYTES, getExtensionLabel, isImageType, supportsTextPreview } from "@/lib/components/chat/file/attachmentUtils";

describe("attachmentUtils — isImageType", () => {
    test("matches image/* mime types", () => {
        expect(isImageType("image/png", "a.png")).toBe(true);
        expect(isImageType("image/jpeg", "a.jpg")).toBe(true);
        expect(isImageType("image/svg+xml", "a.svg")).toBe(true);
    });

    test("matches known image extensions when mime is generic", () => {
        expect(isImageType("application/octet-stream", "photo.PNG")).toBe(true);
        expect(isImageType("application/octet-stream", "photo.webp")).toBe(true);
        expect(isImageType("application/octet-stream", "icon.ico")).toBe(true);
    });

    test("rejects non-image types", () => {
        expect(isImageType("text/plain", "a.txt")).toBe(false);
        expect(isImageType("application/pdf", "a.pdf")).toBe(false);
        expect(isImageType("application/zip", "a.zip")).toBe(false);
    });

    test("handles missing filename", () => {
        expect(isImageType("image/png")).toBe(true);
        expect(isImageType("application/octet-stream")).toBe(false);
    });
});

describe("attachmentUtils — supportsTextPreview", () => {
    test("matches text/* mime types", () => {
        expect(supportsTextPreview("text/plain")).toBe(true);
        expect(supportsTextPreview("text/markdown")).toBe(true);
        expect(supportsTextPreview("text/csv")).toBe(true);
    });

    test("matches structured-text mime keywords", () => {
        expect(supportsTextPreview("application/json")).toBe(true);
        expect(supportsTextPreview("application/xml")).toBe(true);
        expect(supportsTextPreview("application/javascript")).toBe(true);
        expect(supportsTextPreview("application/x-yaml")).toBe(true);
    });

    // CRITICAL INVARIANT: PPTX/DOCX mime types contain "xml" (from
    // "…presentationml…", "…wordprocessingml…"), so this function returns
    // true for them. Callers MUST filter docs out first:
    //   isText = !isDoc && !isImage && supportsTextPreview(mime, filename)
    // Changing this helper to reject Office XML mimes would hide the
    // invariant that callers depend on ordering.
    test("returns true for PPTX/DOCX mime types (caller must pre-filter)", () => {
        expect(supportsTextPreview("application/vnd.openxmlformats-officedocument.presentationml.presentation")).toBe(true);
        expect(supportsTextPreview("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe(true);
        expect(supportsTextPreview("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")).toBe(true);
    });

    test("matches known text extensions when mime is generic", () => {
        expect(supportsTextPreview("application/octet-stream", "notes.txt")).toBe(true);
        expect(supportsTextPreview("application/octet-stream", "script.py")).toBe(true);
        expect(supportsTextPreview("application/octet-stream", "config.TOML")).toBe(true);
    });

    test("rejects binary types with no matching extension", () => {
        expect(supportsTextPreview("application/pdf", "a.pdf")).toBe(false);
        expect(supportsTextPreview("image/png", "a.png")).toBe(false);
        expect(supportsTextPreview("application/zip", "a.zip")).toBe(false);
    });
});

describe("attachmentUtils — getExtensionLabel", () => {
    test("uppercases the extension", () => {
        expect(getExtensionLabel("photo.png")).toBe("PNG");
        expect(getExtensionLabel("README.md")).toBe("MD");
    });

    test("truncates extensions longer than 4 chars", () => {
        expect(getExtensionLabel("slides.pptx")).toBe("PPTX");
        expect(getExtensionLabel("bundle.tarball")).toBe("TARB");
    });

    test("falls back to FILE for extensionless names", () => {
        expect(getExtensionLabel("Makefile")).toBe("FILE");
    });
});

describe("attachmentUtils — MAX_THUMBNAIL_FILE_BYTES", () => {
    test("is 20 MB", () => {
        expect(MAX_THUMBNAIL_FILE_BYTES).toBe(20 * 1024 * 1024);
    });
});
