export type UserRole = "Super Admin" | "Company Admin" | "Analyst" | "Viewer";

export interface CompanySummary {
  id: number;
  name: string;
  industry: string;
  email: string;
}

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  status: string;
  lastLogin: string | null;
  company: CompanySummary;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  companyName: string;
  industry: string;
  companyEmail: string;
  companyAddress: string;
  companyPhoneNumber: string;
  ownerName: string;
  ownerEmail: string;
  password: string;
  confirmPassword: string;
}

export interface AuthResponse extends AuthTokens {
  user: AuthUser;
}
