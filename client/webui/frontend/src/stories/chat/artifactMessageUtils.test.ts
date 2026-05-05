import { describe, test, expect } from "vitest";

import { isArtifactDeleted } from "@/lib/components/chat/file/artifactMessageUtils";
import type { ArtifactInfo, FileAttachment, MessageFE } from "@/lib/types";

const artifact: ArtifactInfo = {
    filename: "report.pdf",
    mime_type: "application/pdf",
    size: 1234,
    last_modified: "2026-01-01T00:00:00Z",
};

const fileAttachmentWithUri: FileAttachment = {
    name: "report.pdf",
    uri: "artifact://session/report.pdf?version=1",
};

const fileAttachmentWithoutUri: FileAttachment = {
    name: "report.pdf",
};

const completeMessage: MessageFE = { isUser: false, isComplete: true, parts: [] };
const inFlightMessage: MessageFE = { isUser: false, isComplete: false, parts: [] };

describe("isArtifactDeleted", () => {
    test("returns false for non-completed status", () => {
        expect(isArtifactDeleted({ status: "in-progress", artifactInfo: undefined, fileAttachment: undefined, message: undefined })).toBe(false);
        expect(isArtifactDeleted({ status: "failed", artifactInfo: undefined, fileAttachment: undefined, message: undefined })).toBe(false);
    });

    test("returns false when artifact is found in the list (even if hidden)", () => {
        expect(isArtifactDeleted({ status: "completed", artifactInfo: artifact, fileAttachment: undefined, message: undefined })).toBe(false);
    });

    test("returns false when fileAttachment has a URI (exists on backend, not yet fetched)", () => {
        expect(isArtifactDeleted({ status: "completed", artifactInfo: undefined, fileAttachment: fileAttachmentWithUri, message: undefined })).toBe(false);
    });

    test("returns false while parent message is still streaming", () => {
        expect(isArtifactDeleted({ status: "completed", artifactInfo: undefined, fileAttachment: fileAttachmentWithoutUri, message: inFlightMessage })).toBe(false);
    });

    test("returns true when completed, not in list, no URI, and message is complete", () => {
        expect(isArtifactDeleted({ status: "completed", artifactInfo: undefined, fileAttachment: fileAttachmentWithoutUri, message: completeMessage })).toBe(true);
    });

    test("returns true when completed, not in list, no URI, and no message provided", () => {
        expect(isArtifactDeleted({ status: "completed", artifactInfo: undefined, fileAttachment: undefined, message: undefined })).toBe(true);
    });
});
