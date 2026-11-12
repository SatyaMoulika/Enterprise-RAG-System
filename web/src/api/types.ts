export interface User {
  id: number;
  email: string;
  role: 'admin' | 'employee';
  enterprise_id: number;
  is_active: boolean;
}
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface RegisterPayload {
  enterprise_name: string;
  email: string;
  password: string;
}
export interface DocumentRecord {
  id: number;
  title: string;
  enterprise_id: number;
  created_at: string;
}
export interface DocumentLimits {
  allowed_extensions: string[];
  max_upload_bytes: number;
}
export interface Citation {
  document_id: number;
  title: string;
  chunk_index: number;
  excerpt: string;
}
export interface Answer {
  answer: string;
  sources: number[];
  citations: Citation[];
}
