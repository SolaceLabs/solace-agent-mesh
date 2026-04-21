/**
 * Shared helpers for attachment card components (FileUploadCard, ArtifactAttachmentCard)
 * and the AttachArtifactDialog. Keeps the PPTX/DOCX-vs-"xml" precedence invariant in one
 * place so the three call sites cannot drift apart.
 */

/** Cap for generating thumbnails in-browser — avoids base64-encoding huge binaries. */
export const MAX_THUMBNAIL_FILE_BYTES = 20 * 1024 * 1024; // 20 MB

const IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico"];

const TEXT_EXTENSIONS = ["txt", "md", "markdown", "json", "yaml", "yml", "xml", "html", "htm", "css", "scss", "js", "jsx", "ts", "tsx", "py", "java", "c", "cpp", "h", "sh", "log", "csv", "tsv", "ini", "toml"];

const TEXT_MIME_KEYWORDS = ["json", "xml", "javascript", "typescript", "markdown", "yaml", "yml"];

function getFileExtension(filename: string): string | undefined {
    return filename.toLowerCase().split(".").pop();
}

export function isImageType(mimeType: string, filename?: string): boolean {
    if (mimeType.startsWith("image/")) return true;
    if (!filename) return false;
    const ext = getFileExtension(filename);
    return !!ext && IMAGE_EXTENSIONS.includes(ext);
}

export function supportsTextPreview(mimeType: string, filename?: string): boolean {
    if (mimeType.startsWith("text/")) return true;
    if (TEXT_MIME_KEYWORDS.some(k => mimeType.includes(k))) return true;
    if (!filename) return false;
    const ext = getFileExtension(filename);
    return !!ext && TEXT_EXTENSIONS.includes(ext);
}

export function getExtensionLabel(filename: string): string {
    const parts = filename.split(".");
    const ext = parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
    return ext.length > 4 ? ext.substring(0, 4) : ext;
}
