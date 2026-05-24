import { useState } from 'react';
import { useSession } from './hooks/useSession';
import { useChat } from './hooks/useChat';
import RoleSelector from './components/RoleSelector';
import ChatWindow from './components/ChatWindow';
import InputBox from './components/InputBox';

export default function App() {
  const [userId, setUserId] = useState('');
  const [inputUserId, setInputUserId] = useState('');

  const {
    roles, sessions, activeRole, displayName, sessionReady,
    setActiveRole, setDisplayName, openSession,
  } = useSession(userId);
  const {
    messages, streaming, isStreaming, sendMessage, stopStreaming,
    loadingHistory, hasMoreHistory, loadMoreHistory,
    voiceEnabled, setVoiceEnabled,
  } = useChat(userId, activeRole, sessionReady);

  if (!userId) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <h2>原神角色扮演</h2>
        <input
          placeholder="输入用户 ID"
          value={inputUserId}
          onChange={(e) => setInputUserId(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && inputUserId.trim() && setUserId(inputUserId.trim())}
          style={{ padding: 8, fontSize: 16, width: 240 }}
        />
        <button
          onClick={() => inputUserId.trim() && setUserId(inputUserId.trim())}
          style={{ marginLeft: 8, padding: '8px 16px', fontSize: 16 }}
        >
          进入
        </button>
      </div>
    );
  }

  const handleSelectRole = async (roleName) => {
    setActiveRole(roleName);
    setDisplayName('');
    const info = await openSession(roleName);
    if (info) setDisplayName(info.display_name);
  };

  const handleSwitchSession = async (roleName, name) => {
    setActiveRole(roleName);
    setDisplayName(name);
    await openSession(roleName);
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <RoleSelector
        roles={roles}
        sessions={sessions}
        activeRole={activeRole}
        onSelectRole={handleSelectRole}
        onSwitchSession={handleSwitchSession}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #ddd', fontWeight: 'bold' }}>
          {displayName || activeRole || '选择角色开始对话'}
        </div>
        <ChatWindow
          messages={messages}
          streaming={streaming}
          loadingHistory={loadingHistory}
          hasMoreHistory={hasMoreHistory}
          onLoadMore={loadMoreHistory}
        />
        <InputBox
          onSend={sendMessage}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          disabled={!activeRole}
          voiceEnabled={voiceEnabled}
          onToggleVoice={() => setVoiceEnabled((v) => !v)}
        />
      </div>
    </div>
  );
}
