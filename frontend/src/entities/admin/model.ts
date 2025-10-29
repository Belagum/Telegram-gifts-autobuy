// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

/**
 * TypeScript models for admin panel.
 */

export interface AuditLog {
  id: number;
  timestamp: string;
  action: string;
  user_id: number | null;
  ip_address: string | null;
  success: boolean;
  details: Record<string, any>;
}

export interface AuditLogList {
  logs: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface SuspiciousActivity {
  severity: "high" | "medium" | "low";
  activity_type: string;
  description: string;
  user_id: number | null;
  username: string | null;
  ip_address: string | null;
  count: number;
  first_seen: string;
  last_seen: string;
  details: Record<string, any>;
}

export interface ErrorStats {
  ip_address: string | null;
  error_count: number;
  unique_actions: number;
  first_error: string;
  last_error: string;
  sample_errors: string[];
}

export interface UserInfo {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string | null;
  last_login: string | null;
  is_locked: boolean;
  failed_attempts: number;
}

export interface DashboardStats {
  total_users: number;
  total_logs: number;
  logs_last_24h: number;
  failed_logins_24h: number;
  successful_logins_24h: number;
  active_sessions: number;
  errors_last_7d: number;
  most_active_users: Array<{ username: string; activity_count: number }>;
}

export interface AuditLogsFilter {
  limit?: number;
  offset?: number;
  action?: string;
  user_id?: number;
  ip_address?: string;
  success?: boolean;
  start_date?: string;
  end_date?: string;
}

