import { useState, useEffect, useCallback } from 'react';
import { fetchRoles, fetchUserSessions, createSession } from '../api/client';

export function useSession(userId) {
  const [roles, setRoles] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeRole, setActiveRole] = useState(null);
  const [displayName, setDisplayName] = useState('');
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    fetchRoles().then(setRoles).catch(console.error);
  }, []);

  useEffect(() => {
    if (userId) {
      fetchUserSessions(userId).then(setSessions).catch(console.error);
    }
  }, [userId]);

  const openSession = useCallback(async (roleName) => {
    if (!userId) return;
    setSessionReady(false);
    const info = await createSession(userId, roleName);
    setDisplayName(info.display_name);
    setActiveRole(roleName);
    setSessions((prev) => {
      if (prev.some((s) => s.role_name === roleName)) return prev;
      return [...prev, { role_name: roleName, display_name: info.display_name }];
    });
    setSessionReady(true);
    return info;
  }, [userId]);

  return {
    roles, sessions, activeRole, displayName, sessionReady,
    setActiveRole, setDisplayName, openSession,
  };
}
