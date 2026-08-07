import type { Modality } from "./types";

/** Canonical limits aligned with Gemini Embedding 2 Preview */
export const MODALITY_LIMITS = {
  maxTextTokens: 8192,
  maxTextWords: 6000,
  maxImagesPerRequest: 6,
  maxVideoSeconds: 120,
  maxAudioSeconds: 80,
  maxPdfPages: 6,
  maxPdfFilesPerRequest: 1,
} as const;

export const ACCEPT_ATTR =
  ".txt,.png,.jpg,.jpeg,.pdf,.mp3,.wav,.mp4,.mov,text/plain,image/png,image/jpeg,application/pdf,audio/mpeg,audio/wav,video/mp4,video/quicktime";

const EXT_TO_MODALITY: Record<string, Modality> = {
  ".txt": "text",
  ".png": "image",
  ".jpg": "image",
  ".jpeg": "image",
  ".pdf": "pdf",
  ".mp3": "audio",
  ".wav": "audio",
  ".mp4": "video",
  ".mov": "video",
};

export function extensionOf(filename: string): string {
  const i = filename.lastIndexOf(".");
  return i >= 0 ? filename.slice(i).toLowerCase() : "";
}

export function modalityFromFile(file: File): Modality | null {
  return EXT_TO_MODALITY[extensionOf(file.name)] ?? null;
}

export function estimateWordCount(text: string): number {
  return text
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

export function validateMessageText(text: string): string | null {
  const words = estimateWordCount(text);
  if (words > MODALITY_LIMITS.maxTextWords) {
    return `Text exceeds ~${MODALITY_LIMITS.maxTextWords} words (${MODALITY_LIMITS.maxTextTokens} tokens).`;
  }
  return null;
}

export async function readMediaDuration(file: File): Promise<number | null> {
  const url = URL.createObjectURL(file);
  const isAudio = file.type.startsWith("audio") || /\.(mp3|wav)$/i.test(file.name);
  try {
    if (isAudio) {
      const audio = document.createElement("audio");
      audio.preload = "metadata";
      audio.src = url;
      await new Promise<void>((resolve, reject) => {
        audio.onloadedmetadata = () => resolve();
        audio.onerror = () => reject(new Error("metadata"));
      });
      return Number.isFinite(audio.duration) ? audio.duration : null;
    }
    const video = document.createElement("video");
    video.preload = "metadata";
    video.src = url;
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error("metadata"));
    });
    return Number.isFinite(video.duration) ? video.duration : null;
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function validateFile(file: File): Promise<string | null> {
  const modality = modalityFromFile(file);
  if (!modality) {
    return `Unsupported type. Allowed: TXT, PNG, JPEG, PDF, MP3, WAV, MP4, MOV.`;
  }
  if (modality === "text") {
    const text = await file.text();
    return validateMessageText(text);
  }
  if (modality === "audio") {
    const duration = await readMediaDuration(file);
    if (duration != null && duration > MODALITY_LIMITS.maxAudioSeconds) {
      return `Audio exceeds ${MODALITY_LIMITS.maxAudioSeconds}s limit.`;
    }
  }
  if (modality === "video") {
    const duration = await readMediaDuration(file);
    if (duration != null && duration > MODALITY_LIMITS.maxVideoSeconds) {
      return `Video exceeds ${MODALITY_LIMITS.maxVideoSeconds}s limit.`;
    }
  }
  return null;
}

export function validateAttachmentBatch(
  modalities: Modality[],
): string | null {
  const images = modalities.filter((m) => m === "image").length;
  const pdfs = modalities.filter((m) => m === "pdf").length;
  if (images > MODALITY_LIMITS.maxImagesPerRequest) {
    return `At most ${MODALITY_LIMITS.maxImagesPerRequest} images per request.`;
  }
  if (pdfs > MODALITY_LIMITS.maxPdfFilesPerRequest) {
    return `At most ${MODALITY_LIMITS.maxPdfFilesPerRequest} PDF per request.`;
  }
  return null;
}
