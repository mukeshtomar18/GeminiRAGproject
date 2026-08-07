"use client";

import { useCallback, useState } from "react";
import { sendChat, uploadFiles } from "@/lib/api";
import { modalityFromFile } from "@/lib/attachments";
import type { ChatMessage, Modality } from "@/lib/types";
import { Composer } from "./Composer";
import { Thread } from "./Thread";

export function ChatShell() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);

  const onUploadFiles = useCallback(
    async (
      files: File[],
      onUploadProgress: (percent: number) => void,
    ) => {
      const names = files.map((f) => f.name).join(", ");
      const noticeId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: noticeId,
          role: "assistant",
          content: `Uploading ${names}…`,
          pending: true,
        },
      ]);

      try {
        const result = await uploadFiles(files, onUploadProgress);
        const attachments = files.map((f) => ({
          name: f.name,
          modality: (modalityFromFile(f) ?? "text") as Modality,
        }));
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== noticeId),
          {
            id: crypto.randomUUID(),
            role: "user",
            content: `Uploaded: ${names}`,
            attachments,
          },
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: result.message,
          },
        ]);
      } catch (err) {
        const detail = err instanceof Error ? err.message : "Upload failed";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === noticeId
              ? { id: noticeId, role: "assistant", content: detail, error: true }
              : m,
          ),
        );
        throw err;
      }
    },
    [],
  );

  const onSendMessage = useCallback(async (message: string) => {
    const userId = crypto.randomUUID();
    const pendingId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", content: message },
      { id: pendingId, role: "assistant", content: "", pending: true },
    ]);
    setBusy(true);

    try {
      const result = await sendChat(message);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: result.answer,
                citations: result.citations,
              }
            : m,
        ),
      );
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Request failed";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: detail,
                error: true,
              }
            : m,
        ),
      );
      throw err;
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <p className="text-sm font-semibold tracking-tight text-slate-50">
            GeminiRAG
          </p>
          <p className="text-xs text-muted">
            Multimodal retrieval · Gemini Embedding 2 · Pinecone
          </p>
          <p className="mt-1 text-[11px] text-amber-200/90">
            Use Upload to index files immediately, then Send to ask questions.
          </p>
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Thread messages={messages} />
      </main>
      <Composer
        disabled={busy}
        onSendMessage={onSendMessage}
        onUploadFiles={onUploadFiles}
      />
    </div>
  );
}
