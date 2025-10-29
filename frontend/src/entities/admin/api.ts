// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Vova Orig

/**
 * API client for admin endpoints.
 */

import { httpClient } from "../../shared/api/httpClient";
import type {
  AuditLog,
  AuditLogList,
  AuditLogsFilter,
  DashboardStats,
  ErrorStats,
  SuspiciousActivity,
  UserInfo,
} from "./model";

/**
 * Get audit logs with filtering and pagination.
 */
export async function getAuditLogs(
  filter: AuditLogsFilter = {}
): Promise<AuditLogList> {
  const params = new URLSearchParams();

  if (filter.limit) params.append("limit", filter.limit.toString());
  if (filter.offset) params.append("offset", filter.offset.toString());
  if (filter.action) params.append("action", filter.action);
  if (filter.user_id) params.append("user_id", filter.user_id.toString());
  if (filter.ip_address) params.append("ip_address", filter.ip_address);
  if (filter.success !== undefined)
    params.append("success", filter.success.toString());
  if (filter.start_date) params.append("start_date", filter.start_date);
  if (filter.end_date) params.append("end_date", filter.end_date);

  const queryString = params.toString();
  const url = queryString
    ? `/admin/audit-logs?${queryString}`
    : "/admin/audit-logs";

  return await httpClient<AuditLogList>(url);
}

/**
 * Get available action categories.
 */
export async function getActionCategories(): Promise<string[]> {
  const data = await httpClient<{ actions: string[] }>(
    "/admin/audit-logs/categories"
  );
  return data.actions;
}

/**
 * Get audit logs for a specific user.
 */
export async function getUserAudit(
  userId: number,
  limit: number = 100
): Promise<AuditLog[]> {
  const url = `/admin/audit-logs/user/${userId}?limit=${limit}`;
  const data = await httpClient<{ logs: AuditLog[] }>(url);
  return data.logs;
}

/**
 * Get suspicious activities.
 */
export async function getSuspiciousActivity(
  limit: number = 50
): Promise<SuspiciousActivity[]> {
  const url = `/admin/suspicious-activity?limit=${limit}`;
  const data = await httpClient<{ activities: SuspiciousActivity[] }>(url);
  return data.activities;
}

/**
 * Get error statistics.
 */
export async function getErrorStats(limit: number = 50): Promise<ErrorStats[]> {
  const url = `/admin/error-stats?limit=${limit}`;
  const data = await httpClient<{ stats: ErrorStats[] }>(url);
  return data.stats;
}

/**
 * Get list of all users.
 */
export async function listUsers(): Promise<UserInfo[]> {
  const data = await httpClient<{ users: UserInfo[] }>("/admin/users");
  return data.users;
}

/**
 * Unlock a user account.
 */
export async function unlockUser(userId: number): Promise<void> {
  await httpClient(`/admin/users/${userId}/unlock`, { method: "POST", body: {} });
}

/**
 * Get dashboard statistics.
 */
export async function getDashboardStats(): Promise<DashboardStats> {
  return await httpClient<DashboardStats>("/admin/dashboard-stats");
}

