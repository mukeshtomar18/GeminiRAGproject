"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/types";
import { Bubble } from "./Bubble";

type Props = {
  messages: ChatMessage[];
};

export function Thread({ messages }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-50">
          GeminiRAG
        </h2>
        <p className="mt-2 max-w-md text-sm text-muted">
          Upload files with the Upload button (they index immediately), then ask a
          question with Send. Supports text, PDF, image, audio, and video.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      {messages.map((m) => (
        <Bubble key={m.id} message={m} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
