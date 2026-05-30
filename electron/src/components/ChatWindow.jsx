// ==================== 依赖导入 ====================
import { useEffect, useLayoutEffect, useRef, useCallback } from 'react';
// Markdown 渲染组件，用于渲染 AI 回复中的格式化文本
import ReactMarkdown from 'react-markdown';

// ==================== 聊天消息展示窗口组件 ====================

/**
 * 聊天消息展示窗口组件
 * 负责显示消息列表、流式输出、自动滚动和历史加载
 * 使用 useLayoutEffect 确保滚动操作在 DOM 更新后立即执行，避免视觉跳动
 *
 * Args:
 *   messages: 消息数组，每条包含 {role: 'user'|'assistant', content: string, audioUrl?: string}
 *   streaming: 当前流式输出的文本（为空字符串表示无流式输出）
 *   loadingHistory: 是否正在加载历史记录
 *   hasMoreHistory: 是否还有更早的历史记录可加载
 *   onLoadMore: 加载更多历史记录的回调函数
 *   roleName: 当前角色名称，用于显示头像
 */
export default function ChatWindow({ messages, streaming, loadingHistory, hasMoreHistory, onLoadMore, roleName }) {
  // ==================== Refs ====================
  // 滚动容器的 DOM 引用
  const containerRef = useRef(null);
  // 底部锚点的 DOM 引用，用于 scrollIntoView 自动滚到底
  const bottomRef = useRef(null);
  // 加载历史前的容器 scrollHeight，用于计算新增内容高度
  const scrollHeightBeforeRef = useRef(0);
  // 标记当前是否正在加载历史（用于区分"加载历史"和"收到新消息"两种消息变化）
  const isLoadingHistoryRef = useRef(false);

  // ==================== 滚动控制逻辑 ====================

  // 阶段1：loadingHistory 变为 true 时，记录当前容器的 scrollHeight
  useLayoutEffect(() => {
    if (loadingHistory) {
      const container = containerRef.current;
      if (container) {
        scrollHeightBeforeRef.current = container.scrollHeight;
      }
      isLoadingHistoryRef.current = true;
    }
  }, [loadingHistory]);

  // 阶段2：messages 数组变化后，根据情况决定滚动行为
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (isLoadingHistoryRef.current) {
      // 情况A：刚加载完历史记录，保持用户当前看到的内容位置不变
      const delta = container.scrollHeight - scrollHeightBeforeRef.current;
      if (delta > 0) {
        container.scrollTop += delta;
      }
      isLoadingHistoryRef.current = false;
    } else if (messages.length > 0) {
      // 情况B：收到新消息，平滑滚动到底部
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // 阶段3：流式输出过程中，每次 streaming 文本变化时滚到底部
  useEffect(() => {
    if (streaming) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [streaming]);

  // ==================== 历史加载触发 ====================

  /**
   * 滚动事件处理：当用户滚动到顶部附近时自动加载更多历史
   * 距离顶部 200px 以内触发加载
   */
  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container || loadingHistory || !hasMoreHistory) return;
    if (container.scrollTop < 200) {
      onLoadMore?.();
    }
  }, [loadingHistory, hasMoreHistory, onLoadMore]);

  // ==================== 渲染 ====================

  // 获取角色名第一个字作为头像
  const avatarChar = roleName ? roleName[0] : '?';

  return (
    <div ref={containerRef} onScroll={handleScroll} style={styles.container}>
      {/* 顶部历史加载提示 */}
      {hasMoreHistory && (
        <div style={styles.loadHint}>
          {loadingHistory ? '加载中...' : '滚动到顶部加载更多历史记录'}
        </div>
      )}
      {!hasMoreHistory && messages.length > 0 && (
        <div style={styles.endHint}>没有更早的记录了</div>
      )}

      {/* ==================== 消息列表 ==================== */}
      {messages.map((msg, i) => (
        <div
          key={i}
          style={{
            ...styles.messageRow,
            // 用户消息右对齐，助手消息左对齐
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}
        >
          {/* 助手头像：显示角色名第一个字 */}
          {msg.role === 'assistant' && (
            <div style={styles.assistantAvatar}>{avatarChar}</div>
          )}

          <div
            style={{
              maxWidth: '70%',
              padding: '10px 14px',
              borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              // 用户消息：深灰色背景白色文字；助手消息：白色背景
              background: msg.role === 'user' ? '#333' : '#fff',
              color: msg.role === 'user' ? '#fff' : '#333',
              boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
              lineHeight: 1.5,
              fontSize: 14,
            }}
          >
            {msg.role === 'assistant' ? (
              <>
                {/* 助手消息：使用 Markdown 渲染 */}
                <ReactMarkdown>{msg.content}</ReactMarkdown>
                {/* 如果消息有关联的语音 URL，显示播放按钮 */}
                {msg.audioUrl && (
                  <button
                    onClick={() => { const a = new Audio(msg.audioUrl); a.play(); }}
                    style={styles.audioBtn}
                    title="播放语音"
                  >
                    🔊
                  </button>
                )}
              </>
            ) : (
              // 用户消息：纯文本显示
              msg.content
            )}
          </div>
        </div>
      ))}

      {/* ==================== 流式输出实时显示 ==================== */}
      {streaming && (
        <div style={{ ...styles.messageRow, justifyContent: 'flex-start' }}>
          <div style={styles.assistantAvatar}>{avatarChar}</div>
          <div style={styles.streamingBox}>
            {/* 流式文本也用 Markdown 渲染 */}
            <ReactMarkdown>{streaming}</ReactMarkdown>
            {/* 闪烁光标 */}
            <span style={styles.cursor}>▊</span>
          </div>
        </div>
      )}

      {/* 底部锚点 */}
      <div ref={bottomRef} />
    </div>
  );
}

const styles = {
  container: {
    flex: 1, overflowY: 'auto', padding: '24px 32px',
    background: '#f0f0f0',
  },
  loadHint: {
    textAlign: 'center', padding: 12, color: '#aaa', fontSize: 12,
  },
  endHint: {
    textAlign: 'center', padding: 12, color: '#ccc', fontSize: 12,
  },
  messageRow: {
    marginBottom: 16, display: 'flex', gap: 10, alignItems: 'flex-start',
  },
  assistantAvatar: {
    width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
    background: '#e0e0e0',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#333', fontSize: 12, fontWeight: 600,
  },
  audioBtn: {
    marginTop: 8, display: 'inline-block', background: 'none',
    border: 'none', cursor: 'pointer', fontSize: 14, color: '#333',
  },
  streamingBox: {
    maxWidth: '70%', padding: '10px 14px', borderRadius: '12px 12px 12px 4px',
    background: '#fff', color: '#333',
    boxShadow: '0 1px 4px rgba(0,0,0,0.06)', lineHeight: 1.5, fontSize: 14,
  },
  cursor: {
    animation: 'blink 1s infinite', color: '#333',
  },
};
