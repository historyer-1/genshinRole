import { useState } from 'react';

export default function InputBox({ onSend, onStop, isStreaming, disabled, voiceEnabled, onToggleVoice }) {
  const [text, setText] = useState('');

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setText('');
  };

  return (
    <div style={{ display: 'flex', padding: 12, borderTop: '1px solid #ddd', gap: 8 }}>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        placeholder={disabled ? '请先选择角色' : '输入消息...'}
        disabled={disabled}
        style={{ flex: 1, padding: 8, fontSize: 14, borderRadius: 8, border: '1px solid #ccc' }}
      />
      <button
        onClick={onToggleVoice}
        disabled={disabled}
        title={voiceEnabled ? '关闭语音' : '开启语音'}
        style={{
          padding: '8px 12px',
          background: voiceEnabled ? '#4caf50' : '#f5f5f5',
          color: voiceEnabled ? '#fff' : '#666',
          border: '1px solid #ccc',
          borderRadius: 8,
          cursor: disabled ? 'not-allowed' : 'pointer',
        }}
      >
        {voiceEnabled ? '🔊' : '🔇'}
      </button>
      {isStreaming ? (
        <button onClick={onStop} style={{ padding: '8px 16px' }}>
          停止
        </button>
      ) : (
        <button onClick={handleSubmit} disabled={disabled || !text.trim()} style={{ padding: '8px 16px' }}>
          发送
        </button>
      )}
    </div>
  );
}
