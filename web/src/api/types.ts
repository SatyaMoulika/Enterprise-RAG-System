export interface User {
  profile_photo?: string | null;
  name?: string;
  id: number;
  email: string;
  role: 'admin' | 'employee';
  enterprise_id: number;
  enterprise_name?: string;
  is_active: boolean;
}
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface RegisterPayload {
  enterprise_name: string;
  name: string;
  is_admin: true;
  email: string;
  password: string;
}
export interface DocumentAccess {
  visibility: 'company' | 'personal' | 'restricted';
  recipient_ids: number[];
}
export interface DocumentRecord {
  index_status?: 'queued' | 'indexing' | 'ready' | 'failed';
  index_error?: string | null;
  extraction_warnings?: string[];
  visibility?: DocumentAccess['visibility'];
  recipient_ids?: number[];
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
  marker?: number;
  page_start?: number | null;
  page_end?: number | null;
  section?: string | null;
  document_id: number;
  title: string;
  chunk_index: number;
  excerpt: string;
}
export interface Answer {
  answer_origin?: string;
  citation_status?: string;
  answer: string;
  sources: number[];
  citations: Citation[];
}

export interface Member extends User {
  created_at: string;
}
export interface CreateMemberPayload {
  name?: string;
  email: string;
  password: string;
  role: 'admin' | 'employee';
}
