"use client";

import {
  FormEvent,
  KeyboardEvent,
  useRef,
  useState,
} from "react";
import {
  ACCEPT_ATTR,
  modalityFromFile,
  validateAttachmentBatch,
  validateFile,
  validateMessageText,
} from "@/lib/attachments";
import type { AttachmentItem } from "@/lib/types";
import { AttachmentChips } from "./AttachMenu";

type Props = {
  disabled?: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onUploadFiles: (
    files: File[],
    onUploadProgress: (percent: number) => void,
  ) => Promise<void>;
};

export function Composer({ disabled, onSendMessage, onUploadFiles }: Props) {
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<AttachmentItem[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function openPicker() {
    fileRef.current?.click();
  }

  async function uploadSelectedFiles(fileList: FileList | File[]) {
    setLocalError(null);
    const incoming = Array.from(fileList);
    if (!incoming.length) return;

    const placeholders: AttachmentItem[] = incoming.map((file) => {
      const modality = modalityFromFile(file) ?? "text";
      return {
        id: crypto.randomUUID(),
        file,
        modality,
        previewUrl:
          modality === "image" ? URL.createObjectURL(file) : undefined,
        status: "validating",
        progress: 0,
      };
    });
    setUploads((prev) => [...prev, ...placeholders]);

    const accepted: AttachmentItem[] = [];
    for (const item of placeholders) {
      const modality = modalityFromFile(item.file);
      if (!modality) {
        accepted.push({
          ...item,
          status: "error",
          error: "Unsupported file type",
        });
        continue;
      }
      const error = await validateFile(item.file);
      accepted.push({
        ...item,
        modality,
        status: error ? "error" : "ready",
        error: error ?? undefined,
        progress: 0,
      });
    }

    setUploads((prev) => {
      const byId = new Map(accepted.map((item) => [item.id, item]));
      return prev.map((item) => byId.get(item.id) ?? item);
    });

    const ready = accepted.filter((a) => a.status === "ready");
    const batchError = validateAttachmentBatch(ready.map((a) => a.modality));
    if (batchError) {
      setLocalError(batchError);
      setUploads((prev) =>
        prev.map((item) =>
          ready.some((r) => r.id === item.id)
            ? { ...item, status: "error", error: batchError }
            : item,
        ),
      );
      return;
    }

    if (!ready.length) {
      setLocalError("No valid files to upload.");
      return;
    }

    setUploading(true);
    setUploads((prev) =>
      prev.map((item) =>
        ready.some((r) => r.id === item.id)
          ? { ...item, status: "uploading", progress: 0 }
          : item,
      ),
    );

    try {
      await onUploadFiles(
        ready.map((r) => r.file),
        (percent) => {
          setUploads((prev) =>
            prev.map((item) =>
              item.status === "uploading"
                ? { ...item, progress: percent }
                : item,
            ),
          );
        },
      );
      setUploads((prev) =>
        prev.map((item) =>
          item.status === "uploading"
            ? { ...item, status: "uploaded", progress: 100 }
            : item,
        ),
      );
      window.setTimeout(() => {
        setUploads((prev) => {
          const keepErrors = prev.filter((p) => p.status === "error");
          for (const item of prev) {
            if (item.status !== "error" && item.previewUrl) {
              URL.revokeObjectURL(item.previewUrl);
            }
          }
          return keepErrors;
        });
      }, 1200);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Upload failed";
      setLocalError(detail);
      setUploads((prev) =>
        prev.map((item) =>
          item.status === "uploading"
            ? { ...item, status: "error", error: detail, progress: item.progress ?? 0 }
            : item,
        ),
      );
    } finally {
      setUploading(false);
    }
  }

  function removeUpload(id: string) {
    setUploads((prev) => {
      const target = prev.find((a) => a.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((a) => a.id !== id);
    });
    setLocalError(null);
  }

  async function handleSubmit(e?: FormEvent) {
    e?.preventDefault();
    if (disabled || uploading || sending) return;

    const message = text.trim();
    if (!message) {
      setLocalError("Type a message to send. Use Upload for files.");
      return;
    }
    const textError = validateMessageText(message);
    if (textError) {
      setLocalError(textError);
      return;
    }

    setLocalError(null);
    setSending(true);
    try {
      await onSendMessage(message);
      setText("");
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Send failed";
      setLocalError(detail);
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  }

  const overallProgress =
    uploads.find((a) => a.status === "uploading")?.progress ?? null;

  return (
    <div
      onDragEnter={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files?.length) {
          void uploadSelectedFiles(e.dataTransfer.files);
        }
      }}
      className={`border-t border-border bg-panel/80 px-4 py-3 backdrop-blur ${
        dragging ? "ring-2 ring-inset ring-accent/50" : ""
      }`}
    >
      <div className="mx-auto max-w-3xl">
        <AttachmentChips
          items={uploads}
          onRemove={removeUpload}
          locked={uploading}
        />

        {(localError || dragging || uploading) && (
          <p
            className={`mb-2 text-xs ${
              localError ? "text-red-300" : "text-accent"
            }`}
          >
            {localError ??
              (uploading
                ? (overallProgress ?? 0) >= 100
                  ? "Upload complete — extracting & indexing…"
                  : `Uploading… ${overallProgress ?? 0}%`
                : "Drop files to upload immediately")}
          </p>
        )}

        <div className="mb-2 flex items-center gap-2">
          <button
            type="button"
            aria-label="Upload files"
            className="flex h-10 items-center gap-1.5 rounded-xl border border-border bg-canvas px-4 text-sm font-medium text-slate-100 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={openPicker}
            disabled={disabled || uploading || sending}
          >
            <span aria-hidden>↑</span>
            {uploading
              ? (overallProgress ?? 0) >= 100
                ? "Indexing…"
                : `Uploading ${overallProgress ?? 0}%`
              : "Upload"}
          </button>
          <span className="text-[11px] text-muted">
            Files upload & index as soon as you select them (separate from Send)
          </span>
          <input
            ref={fileRef}
            type="file"
            accept={ACCEPT_ATTR}
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) void uploadSelectedFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>

        <form
          onSubmit={(e) => void handleSubmit(e)}
          className="flex items-end gap-2 rounded-2xl border border-border bg-canvas px-2 py-2"
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask about your indexed files…"
            disabled={disabled || sending}
            className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent py-2 text-sm text-slate-100 outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            disabled={disabled || sending || uploading || !text.trim()}
            className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </form>

        <p className="mt-2 text-[11px] text-muted">
          Upload indexes files now. Send asks questions only. Limits: text ~8,192
          tokens · ≤6 PNG/JPEG · PDF auto-split every 6 pages · audio ≤80s · video
          ≤120s
        </p>
      </div>
    </div>
  );
}
