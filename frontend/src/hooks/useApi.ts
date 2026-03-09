import { useState, useEffect, useCallback, useRef } from 'react';

interface ApiState<T> { data: T | null; error: string | null; isLoading: boolean; }

export function useApi<T = any>(url: string, options?: RequestInit) {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, isLoading: true });
  const abortRef = useRef<AbortController>();

  const fetchData = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
      const res = await fetch(url, {
        ...options, signal: abortRef.current.signal,
        headers: { 'Content-Type': 'application/json', ...(tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}), ...options?.headers },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState({ data, error: null, isLoading: false });
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      setState({ data: null, error: err.message || 'Request failed', isLoading: false });
    }
  }, [url]);

  useEffect(() => { fetchData(); return () => abortRef.current?.abort(); }, [fetchData]);

  return { ...state, refetch: fetchData, mutate: (data: T) => setState(prev => ({ ...prev, data })) };
}

export function usePaginated<T = any>(baseUrl: string, pageSize = 20) {
  const [page, setPage] = useState(1);
  const [state, setState] = useState<{ data: T[]; total: number; isLoading: boolean; error: string | null }>({
    data: [], total: 0, isLoading: true, error: null,
  });

  const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true }));
    try {
      const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
      const res = await fetch(`${baseUrl}?page=${page}&page_size=${pageSize}`, {
        headers: { ...(tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setState({ data: json.results || json.data || [], total: json.count || json.total || 0, isLoading: false, error: null });
    } catch (err: any) {
      setState(prev => ({ ...prev, isLoading: false, error: err.message }));
    }
  }, [baseUrl, page, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { ...state, page, pageSize, setPage, refetch: fetchData, totalPages: Math.ceil(state.total / pageSize), hasNext: page * pageSize < state.total, hasPrev: page > 1 };
}

export function useMutation<TData = any>(url: string, method: string = 'POST') {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = async (data?: TData) => {
    setIsLoading(true); setError(null);
    try {
      const tokens = JSON.parse(localStorage.getItem('auth_tokens') || 'null');
      const res = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json', ...(tokens?.access ? { Authorization: `Bearer ${tokens.access}` } : {}) },
        body: data ? JSON.stringify(data) : undefined,
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`); }
      return await res.json();
    } catch (err: any) {
      setError(err.message); throw err;
    } finally { setIsLoading(false); }
  };

  return { mutate, isLoading, error, reset: () => setError(null) };
}
