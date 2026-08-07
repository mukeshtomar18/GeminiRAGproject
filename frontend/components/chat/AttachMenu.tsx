"use client";

import type { AttachmentItem, AttachmentStatus } from "@/lib/types";

type MenuProps = {
  open: boolean;
  onPick: () => void;
  onClose: () => void;
};

export function AttachMenu({ open, onPick, onClose }: MenuProps) {
  if (!open) return null;

  return (
    <div
      className="absolute bottom-full left-0 mb-2 w-64 animate-fadeUp rounded-xl border border-border bg-panel p-2 shadow-xl"
      role="menu"
    >
      <button
        type="button"
        className="w-full rounded-lg px-3 py-2 text-left text-sm text-slate-100 hover:bg-white/5"
        onClick={() => {
          onPick();
          onClose();
        }}
      >
        Choose files
        <span className="mt-0.5 block text-xs text-muted">
          TXT · PNG/JPEG · PDF · MP3/WAV · MP4/MOV
        </span>
      </button>
    </div>
  );
}

function statusLabel(status: AttachmentStatus, progress?: number): string {
  switch (status) {
    case "validating":
      return "Checking…";
    case "ready":
      return "Ready to upload";
    case "uploading":
      return `Uploading ${progress ?? 0}%`;
    case "uploaded":
      return "Uploaded";
    case "error":
      return "Failed";
    default:
      return status;
  }
}

function statusClass(status: AttachmentStatus): string {
  switch (status) {
    case "error":
      return "border-red-500/50 bg-red-950/40 text-red-100";
    case "uploading":
      return "border-accent/40 bg-accent/10 text-slate-100";
    case "uploaded":
      return "border-emerald-500/40 bg-emerald-950/30 text-emerald-100";
    case "validating":
      return "border-border bg-panel text-slate-300";
    default:
      return "border-border bg-panel text-slate-200";
  }
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

type ChipsProps = {
  items: AttachmentItem[];
  onRemove: (id: string) => void;
  locked?: boolean;
};

export function AttachmentChips({ items, onRemove, locked }: ChipsProps) {
  if (!items.length) return null;

  return (
    <div className="mb-2 space-y-2 px-1">
      {items.map((item) => (
        <div
          key={item.id}
          className={`overflow-hidden rounded-xl border ${statusClass(item.status)}`}
        >
          <div className="flex max-w-full items-center gap-2 px-2.5 py-1.5 text-xs">
            {item.previewUrl && item.modality === "image" ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={item.previewUrl}
                alt=""
                className="h-8 w-8 rounded object-cover"
              />
            ) : (
              <span className="rounded bg-accent/15 px-1.5 py-0.5 text-accent">
                {item.modality}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{item.file.name}</p>
              <p className="truncate text-[11px] opacity-80">
                {statusLabel(item.status, item.progress)}
                {" · "}
                {formatBytes(item.file.size)}
                {item.error ? ` · ${item.error}` : ""}
              </p>
            </div>
            {!locked && item.status !== "uploading" && (
              <button
                type="button"
                aria-label={`Remove ${item.file.name}`}
                className="ml-1 rounded px-1 text-muted hover:bg-white/10 hover:text-slate-100"
                onClick={() => onRemove(item.id)}
              >
                ×
              </button>
            )}
          </div>
          {(item.status === "uploading" || item.status === "validating") && (
            <div className="h-1 w-full bg-black/20">
              <div
                className={`h-full transition-all duration-200 ${
                  item.status === "validating"
                    ? "w-1/3 animate-pulse bg-muted"
                    : "bg-accent"
                }`}
                style={
                  item.status === "uploading"
                    ? { width: `${item.progress ?? 0}%` }
                    : undefined
                }
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
