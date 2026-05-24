import { useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';

export default function ChatWindow({ messages, streaming, loadingHistory, hasMoreHistory, onLoadMore }) {
  const containerRef = useRef(null);
  const bottomRef = useRef(null);
  const scrollHeightBeforeRef = useRef(0);
  const isLoadingHistoryRef = useRef(false);

  // loadingHistory 变为 true 时记录容器高度
  useLayoutEffect(() => {
    if (loadingHistory) {
      const container = containerRef.current;
      if (container) {
        scrollHeightBeforeRef.current = container.scrollHeight;
      }
      isLoadingHistoryRef.current = true;
    }
  }, [loadingHistory]);

  // 消息列表变化后：加载历史时保持位置，新消息时滚到底
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (isLoadingHistoryRef.current) {
      // 刚加载完历史，保持滚动位置不变
      const delta = container.scrollHeight - scrollHeightBeforeRef.current;
      if (delta > 0) {
        container.scrollTop += delta;
      }
      isLoadingHistoryRef.current = false;
    } else if (messages.length > 0) {
      // 新消息到来，滚到底部
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // 流式输出时滚到底部
  useEffect(() => {
    if (streaming) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [streaming]);

  // 滚动到顶部附近时自动加载更多历史
  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container || loadingHistory || !hasMoreHistory) return;
    if (container.scrollTop < 200) {
      onLoadMore?.();
    }
  }, [loadingHistory, hasMoreHistory, onLoadMore]);

  return (
    <div ref={containerRef} onScroll={handleScroll} style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
      {hasMoreHistory && (
        <div style={{ textAlign: 'center', padding: 8, color: '#999', fontSize: 13 }}>
          {loadingHistory ? '加载中...' : '滚动到顶部加载更多历史记录'}
        </div>
      )}
      {!hasMoreHistory && messages.length > 0 && (
        <div style={{ textAlign: 'center', padding: 8, color: '#ccc', fontSize: 13 }}>
          ── 没有更早的记录了 ──
        </div>
      )}

      {messages.map((msg, i) => (
        <div
          key={i}
          style={{
            marginBottom: 12,
            display: 'flex',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}
        >
          <div
            style={{
              maxWidth: '75%',
              padding: '8px 12px',
              borderRadius: 12,
              background: msg.role === 'user' ? '#1976d2' : '#f5f5f5',
              color: msg.role === 'user' ? '#fff' : '#333',
            }}
          >
            {msg.role === 'assistant' ? (
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            ) : (
              msg.content
            )}
          </div>
        </div>
      ))}

      {streaming && (
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-start' }}>
          <div
            style={{
              maxWidth: '75%',
              padding: '8px 12px',
              borderRadius: 12,
              background: '#f5f5f5',
              color: '#333',
            }}
          >
            <ReactMarkdown>{streaming}</ReactMarkdown>
            <span style={{ animation: 'blink 1s infinite' }}>▊</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
