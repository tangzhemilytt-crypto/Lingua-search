export type Document = {
  id: string;
  title: string;
  filename: string;
  size_bytes: number;
  pages: number;
  created_at: string;
  sample: number;
  chunks: number;
};
export type Passage = { id: string; page: number; text: string };
export type Source = Passage & {
  document_id: string;
  title: string;
  filename: string;
  sample: number;
  score: number;
  number?: number;
};
export type Answer = { answer: string; citations: Source[]; mode: string; notice?: string; cached?: boolean };
export type Config = {
  mode: "demo" | "ai";
  auth_required: boolean;
  public_demo_enabled?: boolean;
  max_demo_model_requests_per_day?: number;
  max_upload_mb: number;
  embedding_model: string | null;
  chat_model?: string | null;
  provider?: "openai" | "gemini" | null;
  max_model_requests_per_day?: number;
};
export const getToken = () => sessionStorage.getItem("lingua-token") || "";
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (getToken() && !path.startsWith("/demo/")) headers.set("Authorization", `Bearer ${getToken()}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Please check your input and try again.`,
      response.status,
    );
  }
  return response.json();
}
export async function download(id: string) {
  const response = await fetch(`/api/documents/${id}/file`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!response.ok)
    throw new Error("Could not download this PDF. Check your workspace token.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${id}.pdf`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
