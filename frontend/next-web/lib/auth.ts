const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const ACCESS_TOKEN_KEY = "enterprise_rag_access_token";

export type UserRole = "viewer" | "maintainer" | "admin";
export type CurrentUser = {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  tenant_id: string;
  tenant_name: string;
  is_platform_admin: boolean;
  is_active: boolean;
};

export function getAccessToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function saveAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(await readDetail(response));
  const payload = await response.json();
  saveAccessToken(payload.access_token);
  return payload.user;
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = getAccessToken();
  if (!token) return null;
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    clearAccessToken();
    return null;
  }
  return response.json();
}

export async function readDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : "请求失败";
  } catch {
    return "请求失败，请稍后重试";
  }
}
