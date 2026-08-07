import type { ChatResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UploadResponse = {
  indexed_count: number;
  message: string;
  items: {
    source_id: string;
    title?: string | null;
    modality: string;
    chunk_index: number;
    file_url?: string | null;
    page_start?: number | null;
    page_end?: number | null;
  }[];
};

function postFormData<T>(
  path: string,
  form: FormData,
  onUploadProgress?: (percent: number) => void,
  timeoutMs = 15 * 60 * 1000,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.timeout = timeoutMs;

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onUploadProgress) return;
      const percent = Math.max(
        0,
        Math.min(100, Math.round((event.loaded / event.total) * 100)),
      );
      onUploadProgress(percent);
    };

    xhr.upload.onload = () => {
      onUploadProgress?.(100);
    };

    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T);
        return;
      }

      const detail =
        data &&
        typeof data === "object" &&
        "detail" in data &&
        typeof (data as { detail: unknown }).detail === "string"
          ? (data as { detail: string }).detail
          : `Request failed (${xhr.status})`;
      reject(new Error(detail));
    };

    xhr.onerror = () =>
      reject(
        new Error(
          "Network error while uploading. If this is a large video, wait and retry — the server may still be indexing.",
        ),
      );
    xhr.ontimeout = () =>
      reject(
        new Error(
          "Upload timed out while processing. Retry once; large videos can take several minutes.",
        ),
      );
    xhr.onabort = () => reject(new Error("Upload aborted"));
    xhr.send(form);
  });
}

/** Immediate file index — separate from chat send */
export async function uploadFiles(
  files: File[],
  onUploadProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return postFormData<UploadResponse>("/api/upload", form, onUploadProgress);
}

/** Message-only chat against already indexed knowledge */
export async function sendChat(message: string): Promise<ChatResponse> {
  const form = new FormData();
  form.append("message", message);
  return postFormData<ChatResponse>("/api/chat", form, undefined, 10 * 60 * 1000);
}

export async function checkHealth(): Promise<{
  status: string;
  gemini_configured: boolean;
  pinecone_configured: boolean;
}> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}
