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
export type Answer = { answer: string; citations: Source[]; mode: string };
export type Config = {
  mode: "demo" | "ai";
  auth_required: boolean;
  max_upload_mb: number;
  embedding_model: string | null;
};
export const getToken = () => sessionStorage.getItem("lingua-token") || "";
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (getToken()) headers.set("Authorization", `Bearer ${getToken()}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Please check your input and try again.`,
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
