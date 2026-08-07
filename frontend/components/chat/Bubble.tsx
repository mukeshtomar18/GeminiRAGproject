import type { ChatMessage } from "@/lib/types";
import { CitationList } from "./CitationList";

type Props = {
  message: ChatMessage;
};

export function Bubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex animate-fadeUp ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[min(100%,42rem)] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isUser
            ? "bg-user text-slate-50"
            : message.error
              ? "border border-red-500/40 bg-red-950/40 text-red-100"
              : "bg-assistant text-slate-100"
        }`}
      >
        {message.attachments && message.attachments.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {message.attachments.map((a) => (
              <span
                key={`${a.name}-${a.modality}`}
                className="rounded-md bg-black/25 px-2 py-0.5 text-[11px] text-slate-200"
              >
                {a.modality}: {a.name}
              </span>
            ))}
          </div>
        )}

        {message.pending ? (
          <div className="flex items-center gap-1.5 py-1 text-muted">
            <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-accent" />
            <span
              className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-accent"
              style={{ animationDelay: "0.2s" }}
            />
            <span
              className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-accent"
              style={{ animationDelay: "0.4s" }}
            />
            <span className="ml-2 text-xs">Thinking…</span>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}

        {!isUser && message.citations && (
          <CitationList citations={message.citations} />
        )}
      </div>
    </div>
  );
}
