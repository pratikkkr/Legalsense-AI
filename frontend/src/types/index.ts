/* API types matching the backend Pydantic schemas. */

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ActSummary {
  id: string;
  slug: string;
  title: string;
  year: number | null;
  total_sections: number;
}

export interface SectionSummary {
  id: string;
  section_number: string;
  title: string;
  chapter: string | null;
}

export interface SectionDetail extends SectionSummary {
  text: string;
  has_state_amendment: boolean;
  act: ActSummary;
}

export interface SearchResultItem {
  section_id: string | null;
  act_title: string;
  act_slug: string;
  section_number: string;
  section_title: string;
  chapter: string | null;
  text_snippet: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
  total: number;
  elapsed_ms: number;
}

export interface Citation {
  act_title: string;
  section_number: string;
  section_title: string;
  text_snippet: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations: Citation[] | null;
  model_used: string | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface ChatResponse {
  conversation_id: string;
  message: Message;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  results_count: number;
  created_at: string;
}
