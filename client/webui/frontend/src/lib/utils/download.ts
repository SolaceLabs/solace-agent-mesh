import type { FileAttachment } from "../types";

export const downloadBlob = (blob: Blob, filename?: string) => {
    try {
        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "download"; // Use file name or default
        document.body.appendChild(a);
        a.click();

        // Clean up
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Error downloading blob:", error);
    }
};

export const downloadFile = (file: FileAttachment) => {
    try {
        // Decode base64 content
        const byteCharacters = atob(file.content as string);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);

        // Create Blob
        const blob = new Blob([byteArray], { type: file.mime_type ?? "application/octet-stream" });

        downloadBlob(blob, file.name);
    } catch (error) {
        console.error("Error creating download link:", error);
    }
};
