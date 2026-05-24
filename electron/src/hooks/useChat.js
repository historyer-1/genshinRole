import { useState, useRef, useCallback, useEffect } from 'react';
import { chatStream, fetchBatchHistory } from '../api/client';

const LOAD_LIMIT = 10;

function splitSentences(text) {
  const parts = text.split(/([。！？…\n]+)/);
  const result = [];
  for (let i = 0; i < parts.length; i += 2) {
    result.push(parts[i] + (parts[i + 1] || ''));
  }
  return result.filter((s) => s.length > 0);
}

export function useChat(userId, roleName, sessionReady) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const controllerRef = useRef(null);
  const offsetRef = useRef(0);
  const pendingTextRef = useRef(null);
  const typewriterTimerRef = useRef(null);

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

    // 清理上一次的打字机
    if (typewriterTimerRef.current) {
      clearTimeout(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    pendingTextRef.current = null;

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setStreaming('');
    setIsStreaming(true);

    let accumulated = '';

    controllerRef.current = chatStream(
      userId,
      roleName,
      text,
      // onToken
      (token) => {
        accumulated += token;
        if (!voiceEnabled) {
          setStreaming(accumulated);
        }
      },
      // onDone
      (fullText) => {
        if (voiceEnabled) {
          pendingTextRef.current = fullText;
          setStreaming('语音生成中...');
        } else {
          setMessages((prev) => [...prev, { role: 'assistant', content: fullText }]);
          setStreaming('');
          setIsStreaming(false);
          controllerRef.current = null;
        }
      },
      // onError
      (err) => {
        pendingTextRef.current = null;
        setMessages((prev) => [...prev, { role: 'assistant', content: `[错误] ${err}` }]);
        setStreaming('');
        setIsStreaming(false);
        controllerRef.current = null;
      },
      // onAudio
      (audioB64, format) => {
        const text = pendingTextRef.current;
        if (!text) return;
        pendingTextRef.current = null;

        const audioBytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0));
        const blob = new Blob([audioBytes], { type: `audio/${format}` });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        audio.addEventListener('loadedmetadata', () => {
          const duration = audio.duration;
          const sentences = splitSentences(text);
          const totalChars = text.length;

          audio.play();

          let idx = 0;
          let revealed = '';

          const revealNext = () => {
            if (idx >= sentences.length) {
              setMessages((prev) => [...prev, { role: 'assistant', content: text, audioUrl: url }]);
              setStreaming('');
              setIsStreaming(false);
              controllerRef.current = null;
              typewriterTimerRef.current = null;
              return;
            }
            revealed += sentences[idx];
            setStreaming(revealed);
            const delay = (sentences[idx].length / totalChars) * duration * 1000;
            idx++;
            typewriterTimerRef.current = setTimeout(revealNext, delay);
          };

          setStreaming(sentences[0]);
          idx = 1;
          const firstDelay = (sentences[0].length / totalChars) * duration * 1000;
          typewriterTimerRef.current = setTimeout(revealNext, firstDelay);
        });

        audio.play().catch(() => {});
      },
      voiceEnabled
    );
  }, [userId, roleName, isStreaming, voiceEnabled]);

  const stopStreaming = useCallback(() => {
    if (typewriterTimerRef.current) {
      clearTimeout(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    if (pendingTextRef.current) {
      setMessages((prev) => [...prev, { role: 'assistant', content: pendingTextRef.current }]);
      pendingTextRef.current = null;
    } else if (streaming && streaming !== '语音生成中...') {
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
    voiceEnabled, setVoiceEnabled,
  };
}
