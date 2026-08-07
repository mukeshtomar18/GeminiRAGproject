import type { Citation } from "@/lib/types";

type Props = {
  citations: Citation[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function mediaSrc(fileUrl?: string | null): string | null {
  if (!fileUrl) return null;
  if (fileUrl.startsWith("http")) return fileUrl;
  return `${API_URL}${fileUrl}`;
}

export function CitationList({ citations }: Props) {
  if (!citations.length) return null;

  return (
    <div className="mt-3 space-y-2 border-t border-border/70 pt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">
        Sources
      </p>
      <ul className="space-y-2">
        {citations.map((c, i) => {
          const src = c.modality === "image" ? mediaSrc(c.file_url) : null;
          return (
            <li
              key={`${c.source_id}-${i}`}
              className="rounded-lg border border-border/60 bg-panel/60 px-3 py-2 text-xs text-slate-300"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-accent/15 px-1.5 py-0.5 text-accent">
                  {c.modality || "unknown"}
                </span>
                <span className="font-medium text-slate-100">
                  {c.title || c.source_id || "source"}
                </span>
                <span className="text-muted">score {c.score.toFixed(3)}</span>
                {c.page_start != null && c.page_end != null ? (
                  <span className="text-muted">
                    pages {c.page_start}-{c.page_end}
                  </span>
                ) : (
                  c.page != null && (
                    <span className="text-muted">page {c.page}</span>
                  )
                )}
              </div>
              {src && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={src}
                  alt={c.title || "Retrieved image"}
                  className="mt-2 max-h-64 w-auto max-w-full rounded-lg border border-border/50 object-contain"
                />
              )}
              {c.text_preview && (
                <p className="mt-1 line-clamp-3 text-muted">{c.text_preview}</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
