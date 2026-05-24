const BASE_URL = 'http://127.0.0.1:8000';

export async function fetchRoles() {
  const res = await fetch(`${BASE_URL}/api/roles`);
  const data = await res.json();
  return data.roles;
}

export async function createSession(userId, roleName) {
  const res = await fetch(`${BASE_URL}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, role_name: roleName }),
  });
  return res.json();
}

export async function fetchHistory(userId, roleName) {
  const res = await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}/history`);
  const data = await res.json();
  return data.history;
}

export async function fetchBatchHistory(userId, roleName, limit = 10, offset = 0) {
  const res = await fetch(
    `${BASE_URL}/api/sessions/${userId}/${roleName}/history/batch?limit=${limit}&offset=${offset}`
  );
  return res.json();
}

export async function deleteSession(userId, roleName) {
  await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}`, { method: 'DELETE' });
}

export async function fetchUserSessions(userId) {
  const res = await fetch(`${BASE_URL}/api/sessions/${userId}`);
  const data = await res.json();
  return data.sessions;
}

export function chatStream(userId, roleName, message, onToken, onDone, onError, onAudio, voice = false) {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, voice }),
        signal: controller.signal,
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventType = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            const jsonStr = line.slice(5).trim();
            try {
              const data = JSON.parse(jsonStr);
              if (eventType === 'token') {
                onToken(data.content);
              } else if (eventType === 'done') {
                onDone(data.content);
              } else if (eventType === 'audio' && onAudio) {
                onAudio(data.audio, data.format);
              } else if (eventType === 'voice_error') {
                console.warn('语音合成失败:', data.detail);
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        onError(e.message);
      }
    }
  })();

  return controller;
}
