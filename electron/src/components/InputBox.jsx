// ==================== 依赖导入 ====================
import { useState } from 'react';

// ==================== 聊天输入框组件 ====================

/**
 * 聊天输入框组件
 * 位于界面底部，包含消息输入框、语音开关按钮和发送/停止按钮
 * 支持回车发送、语音合成切换、流式输出停止等功能
 *
 * Args:
 *   onSend: 发送消息的回调函数，参数为去除首尾空格的消息文本
 *   onStop: 停止流式输出的回调函数
 *   isStreaming: 是否正在流式输出中（为 true 时显示停止按钮）
 *   voiceEnabled: 是否启用语音合成（影响按钮样式和图标）
 *   onToggleVoice: 切换语音开关的回调函数
 */
export default function InputBox({ onSend, onStop, isStreaming, voiceEnabled, onToggleVoice }) {
  // ==================== 状态 ====================
  // 输入框中的文本内容
  const [text, setText] = useState('');

  // ==================== 事件处理 ====================

  /**
   * 提交消息
   * 去除首尾空格后调用 onSend，然后清空输入框
   * 空消息或流式输出中时不提交
   */
  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setText('');
  };

  // ==================== 渲染 ====================

  return (
    <div style={styles.container}>
      {/* 输入框容器 */}
      <div style={styles.inputWrapper}>
        {/* 消息输入框 */}
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="输入消息..."
          style={styles.input}
        />

        {/* 语音开关 */}
        <div style={styles.voiceGroup}>
          <span style={styles.voiceLabel}>语音</span>
          <div
            style={{
              ...styles.toggle,
              background: voiceEnabled ? '#333' : '#ddd',
            }}
            onClick={onToggleVoice}
          >
            <div style={{
              ...styles.toggleDot,
              left: voiceEnabled ? 18 : 2,
            }} />
          </div>
        </div>

        {/* 发送/停止按钮 */}
        {isStreaming ? (
          <button onClick={onStop} style={styles.stopBtn}>
            停止
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!text.trim()}
            style={{
              ...styles.sendBtn,
              opacity: !text.trim() ? 0.5 : 1,
            }}
          >
            发送
          </button>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    padding: '16px 24px', borderTop: '1px solid #e0e0e0',
    background: '#fff',
  },
  inputWrapper: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '6px 6px 6px 14px',
    background: '#f5f5f5', borderRadius: 10,
  },
  input: {
    flex: 1, padding: '8px 0', fontSize: 14, border: 'none',
    outline: 'none', background: 'transparent',
  },
  voiceGroup: {
    display: 'flex', alignItems: 'center', gap: 6,
  },
  voiceLabel: {
    fontSize: 12, color: '#888',
  },
  toggle: {
    width: 36, height: 20, borderRadius: 10,
    cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
  },
  toggleDot: {
    width: 16, height: 16, borderRadius: '50%', background: '#fff',
    position: 'absolute', top: 2,
    transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
  },
  sendBtn: {
    padding: '8px 18px', fontSize: 13, fontWeight: 600,
    border: 'none', borderRadius: 8, background: '#333', color: '#fff',
    cursor: 'pointer',
  },
  stopBtn: {
    padding: '8px 18px', fontSize: 13, fontWeight: 600,
    border: 'none', borderRadius: 8, background: '#888', color: '#fff',
    cursor: 'pointer',
  },
};
