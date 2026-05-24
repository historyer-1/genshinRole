import { useState, useRef, useCallback, useEffect } from 'react';
import { chatStream, fetchBatchHistory } from '../api/client';

const LOAD_LIMIT = 10;

export function useChat(userId, roleName, sessionReady) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const controllerRef = useRef(null);
  const offsetRef = useRef(0);

  // 会话就绪后自动加载最近的历史记录
  useEffect(() => {
    if (!userId || !roleName || !sessionReady) return;
    setLoadingHistory(true);
    offsetRef.current = 0;
    fetchBatchHistory(userId, roleName, LOAD_LIMIT, 0)
      .then((data) => {
        const history = data.history || [];
        setMessages(history);
        offsetRef.current = history.length;
        setHasMoreHistory(history.length >= LOAD_LIMIT);
      })
      .catch((e) => console.error('加载历史记录失败:', e))
      .finally(() => setLoadingHistory(false));
  }, [userId, roleName, sessionReady]);

  // 切换角色时清空消息
  useEffect(() => {
    if (!roleName) {
      setMessages([]);
      setHasMoreHistory(true);
      offsetRef.current = 0;
    }
  }, [roleName]);

  const sendMessage = useCallback((text) => {
    if (!userId || !roleName || isStreaming) return;

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setStreaming('');
    setIsStreaming(true);

    let accumulated = '';

    controllerRef.current = chatStream(
      userId,
      roleName,
      text,
      (token) => {
        accumulated += token;
        setStreaming(accumulated);
      },
      (fullText) => {
        setMessages((prev) => [...prev, { role: 'assistant', content: fullText }]);
        setStreaming('');
        setIsStreaming(false);
        controllerRef.current = null;
      },
      (err) => {
        setMessages((prev) => [...prev, { role: 'assistant', content: `[错误] ${err}` }]);
        setStreaming('');
        setIsStreaming(false);
        controllerRef.current = null;
      }
    );
  }, [userId, roleName, isStreaming]);

  const stopStreaming = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    if (streaming) {
      setMessages((prev) => [...prev, { role: 'assistant', content: streaming }]);
    }
    setStreaming('');
    setIsStreaming(false);
  }, [streaming]);

  // 加载更早的历史记录
  const loadMoreHistory = useCallback(async () => {
    if (!userId || !roleName || loadingHistory || !hasMoreHistory) return;
    setLoadingHistory(true);
    try {
      const data = await fetchBatchHistory(userId, roleName, LOAD_LIMIT, offsetRef.current);
      const older = data.history || [];
      setMessages((prev) => [...older, ...prev]);
      offsetRef.current += older.length;
      setHasMoreHistory(older.length >= LOAD_LIMIT);
    } catch (e) {
      console.error('加载更多历史记录失败:', e);
    } finally {
      setLoadingHistory(false);
    }
  }, [userId, roleName, loadingHistory, hasMoreHistory]);

  return {
    messages, setMessages, streaming, isStreaming, sendMessage, stopStreaming,
    loadingHistory, hasMoreHistory, loadMoreHistory,
  };
}
