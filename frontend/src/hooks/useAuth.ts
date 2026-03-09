import { useState, useEffect, useCallback } from 'react';

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  avatar?: string;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const TOKEN_KEY = 'auth_tokens';

const getTokens = () => {
  try { return JSON.parse(localStorage.getItem(TOKEN_KEY) || 'null'); }
  catch { return null; }
};

export const useAuth = () => {
  const [state, setState] = useState<AuthState>({ user: null, isLoading: true, isAuthenticated: false });

  const fetchUser = useCallback(async () => {
    const tokens = getTokens();
    if (!tokens?.access) { setState({ user: null, isLoading: false, isAuthenticated: false }); return; }
    try {
      const res = await fetch('/api/v1/auth/me/', {
        headers: { Authorization: `Bearer ${tokens.access}` },
      });
      if (!res.ok) throw new Error('Unauthorized');
      const user = await res.json();
      setState({ user, isLoading: false, isAuthenticated: true });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setState({ user: null, isLoading: false, isAuthenticated: false });
    }
  }, []);

  useEffect(() => { fetchUser(); }, [fetchUser]);

  const login = async (email: string, password: string) => {
    const res = await fetch('/api/v1/auth/login/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) { const data = await res.json(); throw new Error(data.detail || 'Login failed'); }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, JSON.stringify(data.tokens));
    setState({ user: data.user, isLoading: false, isAuthenticated: true });
  };

  const register = async (userData: Record<string, string>) => {
    const res = await fetch('/api/v1/auth/register/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData),
    });
    if (!res.ok) { const data = await res.json(); throw new Error(data.detail || 'Registration failed'); }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, JSON.stringify(data.tokens));
    setState({ user: data.user, isLoading: false, isAuthenticated: true });
  };

  const logout = () => {
    const tokens = getTokens();
    if (tokens?.refresh) {
      fetch('/api/v1/auth/logout/', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokens.access}` },
        body: JSON.stringify({ refresh: tokens.refresh }),
      }).catch(() => {});
    }
    localStorage.removeItem(TOKEN_KEY);
    setState({ user: null, isLoading: false, isAuthenticated: false });
  };

  const updateProfile = async (data: Partial<User>) => {
    const tokens = getTokens();
    const res = await fetch('/api/v1/auth/me/', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokens.access}` },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Update failed');
    const updated = await res.json();
    setState(prev => ({ ...prev, user: updated }));
  };

  return { ...state, login, register, logout, updateProfile, refetch: fetchUser };
};
