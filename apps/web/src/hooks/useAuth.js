import { useCallback, useEffect, useMemo, useState } from "react";
import { getCurrentUser, login, logout, register } from "../api/auth.js";
import { ApiError } from "../api/client.js";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async (signal) => {
    setIsLoading(true);
    try {
      const nextUser = await getCurrentUser(signal);
      setUser(nextUser);
      setError(null);
      return nextUser;
    } catch (caught) {
      if (!signal?.aborted) {
        setUser(null);
        if (!(caught instanceof ApiError && caught.status === 401)) setError(caught);
      }
      return null;
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const signIn = useCallback(async (input) => {
    const result = await login(input);
    setUser(result.user);
    setError(null);
    return result.user;
  }, []);

  const signUp = useCallback(async (input) => {
    const result = await register(input);
    setUser(result.user);
    setError(null);
    return result.user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      setUser(null);
      setError(null);
    }
  }, []);

  const permissions = useMemo(() => new Set(user?.permissions || []), [user]);
  const hasPermission = useCallback(
    (permission) => permissions.has("*") || permissions.has(permission),
    [permissions],
  );

  return {
    user,
    isLoading,
    error,
    hasPermission,
    refresh,
    signIn,
    signUp,
    signOut,
  };
}
