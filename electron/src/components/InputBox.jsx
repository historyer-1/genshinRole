import { useState } from 'react';

export default function InputBox({ onSend, onStop, isStreaming, disabled }) {
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
