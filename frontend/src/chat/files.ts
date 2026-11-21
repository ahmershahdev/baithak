import type { components } from "../api/schema";

export type Attachment = components["schemas"]["Attachment"];

// The server's limit (apps/core/files.py); checked here only to fail fast.
export const MAX_FILE_SIZE = 25 * 1024 * 1024;
export const MAX_FILES = 10;

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function isImage(attachment: Attachment): boolean {
  return attachment.content_type.startsWith("image/");
}

/** Why a picked file won't be uploaded, before trying. */
export function fileProblem(file: { size: number }): string | null {
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_FILE_SIZE) return "Files can be up to 25 MB.";
  return null;
}

/** An image's box at most `max` wide or tall, so the page doesn't jump when it loads. */
export function fitWithin(
  width: number | null,
  height: number | null,
  max: number,
): { width: number; height: number } | null {
  if (!width || !height) return null;
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}
