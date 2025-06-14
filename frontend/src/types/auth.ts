export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: 'user' | 'admin' | 'super_admin';
  is_active: boolean;
  is_verified: boolean;
  profile_picture_url?: string;
  bio?: string;
  company?: string;
  job_title?: string;
  created_at: string;
  last_login_at?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  full_name?: string;
  password: string;
  company?: string;
  job_title?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
}