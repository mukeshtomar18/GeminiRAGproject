export type Modality = "text" | "image" | "audio" | "video" | "pdf";

export type Citation = {
  source_id: string;
  modality: string;
  score: number;
  text_preview: string;
  title?: string | null;
  page?: number | null;
  page_start?: number | null;
  page_end?: number | null;
  mime_type?: string | null;
  file_url?: string | null;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  indexed_count: number;
};

export type AttachmentStatus =
  | "validating"
  | "ready"
  | "uploading"
  | "uploaded"
  | "error";

export type AttachmentItem = {
  id: string;
  file: File;
  modality: Modality;
  previewUrl?: string;
  status: AttachmentStatus;
  error?: string;
  progress?: number;
};

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  attachments?: { name: string; modality: Modality }[];
  citations?: Citation[];
  pending?: boolean;
  error?: boolean;
};
