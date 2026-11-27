export type ChatRole = "user" | "assistant";
export type ChatRunStatus = "completed" | "failed";
export type ToolRunStatus = "ok" | "error";

export interface ToolRun {
  name: string;
  arguments: Record<string, unknown>;
  output: Record<string, unknown>;
  status: ToolRunStatus;
  error_code: string | null;
}

export interface ChatMessage {
  id: number;
  role: ChatRole;
  content: string;
  status: ChatRunStatus;
  error_code: string | null;
  created_at: string;
  tool_runs: ToolRun[];
}

export interface ChatHistory {
  session_id: string;
  messages: ChatMessage[];
}

export interface ChatTurn {
  session_id: string;
  message: ChatMessage;
}
