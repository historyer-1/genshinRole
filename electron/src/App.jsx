import { useState } from 'react';
import { useSession } from './hooks/useSession';
import { useChat } from './hooks/useChat';
import RoleSelector from './components/RoleSelector';
import ChatWindow from './components/ChatWindow';
import InputBox from './components/InputBox';
import NewSessionDialog from './components/NewSessionDialog';

/**
 * 应用根组件
 * 管理用户登录流程，组合会话管理和聊天逻辑，渲染整体布局
 */
export default function App() {
  const [userId, setUserId] = useState('');
  const [inputUserId, setInputUserId] = useState('');
  const [showDialog, setShowDialog] = useState(false);

  const {
    roles, sessions, activeRole, displayName, sessionReady,
    setActiveRole, setDisplayName, openSession,
  } = useSession(userId);

  const {
    messages, streaming, isStreaming, sendMessage, stopStreaming,
    loadingHistory, hasMoreHistory, loadMoreHistory,
    voiceEnabled, setVoiceEnabled,
  } = useChat(userId, activeRole, sessionReady);

  // 登录界面
  if (!userId) {
    return (
      <div style={styles.loginPage}>
        <div style={styles.loginCard}>
          <div style={styles.loginLogo}>
            <div style={styles.logoCircle}>✦</div>
          </div>
          <h1 style={styles.loginTitle}>原神角色扮演</h1>
          <p style={styles.loginSubtitle}>与你喜爱的角色进行对话</p>

          <div style={styles.inputGroup}>
            <input
              style={styles.loginInput}
              placeholder="输入用户 ID"
              value={inputUserId}
              onChange={(e) => setInputUserId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && inputUserId.trim() && setUserId(inputUserId.trim())}
              autoFocus
            />
            <button
              style={styles.loginBtn}
              onClick={() => inputUserId.trim() && setUserId(inputUserId.trim())}
            >
              开始对话
            </button>
          </div>

          <p style={styles.loginHint}>输入任意用户 ID 即可开始</p>
        </div>
      </div>
    );
  }

  // 切换已有会话
  const handleSwitch = (roleName, name) => {
    setActiveRole(roleName);
    setDisplayName(name);
    openSession(roleName);
  };

  // 新建会话
  const handleCreate = async ({ roleName, voiceEnabled: voice }) => {
    setShowDialog(false);
    setVoiceEnabled(voice);
    const info = await openSession(roleName);
    if (info) setDisplayName(info.display_name);
  };

  return (
    <div style={styles.app}>
      {/* 左侧栏 */}
      <RoleSelector
        sessions={sessions}
        activeRole={activeRole}
        onSwitchSession={handleSwitch}
        onNewSession={() => setShowDialog(true)}
      />

      {/* 右侧聊天区 */}
      <div style={styles.main}>
        {activeRole ? (
          <>
            {/* 顶部栏 */}
            <div style={styles.topBar}>
              <div style={styles.topBarLeft}>
                <div style={styles.topBarAvatar}>
                  {(displayName || activeRole)[0]}
                </div>
                <span style={styles.topBarTitle}>{displayName || activeRole}</span>
              </div>
            </div>

            {/* 消息区 */}
            <ChatWindow
              messages={messages}
              streaming={streaming}
              loadingHistory={loadingHistory}
              hasMoreHistory={hasMoreHistory}
              onLoadMore={loadMoreHistory}
              roleName={displayName || activeRole}
            />

            {/* 输入框 */}
            <InputBox
              onSend={sendMessage}
              onStop={stopStreaming}
              isStreaming={isStreaming}
              voiceEnabled={voiceEnabled}
              onToggleVoice={() => setVoiceEnabled((v) => !v)}
            />
          </>
        ) : (
          <div style={styles.emptyState}>
            <div style={styles.emptyLogo}>✦</div>
            <h2 style={styles.emptyTitle}>开始对话</h2>
            <p style={styles.emptyHint}>选择角色或创建新会话</p>

            <div style={styles.quickActions}>
              <div style={styles.quickCard} onClick={() => setShowDialog(true)}>
                <span style={styles.quickIcon}>+</span>
                <span style={styles.quickText}>新建会话</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 新建会话对话框 */}
      {showDialog && (
        <NewSessionDialog
          roles={roles}
          existingRoles={sessions.map((s) => s.role_name)}
          onConfirm={handleCreate}
          onClose={() => setShowDialog(false)}
        />
      )}
    </div>
  );
}

const styles = {
  app: { display: 'flex', height: '100vh', background: '#f0f0f0' },

  // 登录页
  loginPage: {
    height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: '#e8e8e8',
  },
  loginCard: {
    background: '#fff', borderRadius: 16, padding: '48px 40px',
    textAlign: 'center', boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    width: 360,
  },
  loginLogo: { marginBottom: 24 },
  logoCircle: {
    width: 56, height: 56, borderRadius: '50%',
    background: '#333',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 24, color: '#fff',
  },
  loginTitle: {
    fontSize: 22, fontWeight: 600, color: '#1a1a1a', margin: '0 0 8px',
  },
  loginSubtitle: { fontSize: 14, color: '#888', margin: '0 0 32px' },
  inputGroup: { display: 'flex', flexDirection: 'column', gap: 12 },
  loginInput: {
    width: '100%', padding: '12px 16px', fontSize: 14,
    border: '1px solid #ddd', borderRadius: 8, outline: 'none',
    boxSizing: 'border-box', background: '#fafafa',
  },
  loginBtn: {
    width: '100%', padding: '12px 0', fontSize: 14, fontWeight: 600,
    border: 'none', borderRadius: 8, background: '#333', color: '#fff',
    cursor: 'pointer',
  },
  loginHint: { fontSize: 12, color: '#aaa', marginTop: 16 },

  // 主界面
  main: { flex: 1, display: 'flex', flexDirection: 'column', background: '#f0f0f0' },
  topBar: {
    padding: '14px 24px', borderBottom: '1px solid #e0e0e0',
    display: 'flex', alignItems: 'center', background: '#fff',
  },
  topBarLeft: { display: 'flex', alignItems: 'center', gap: 10 },
  topBarAvatar: {
    width: 32, height: 32, borderRadius: '50%',
    background: '#e0e0e0',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#333', fontSize: 13, fontWeight: 600,
  },
  topBarTitle: { fontSize: 15, fontWeight: 600, color: '#1a1a1a' },

  // 空状态
  emptyState: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
  },
  emptyLogo: { fontSize: 36, marginBottom: 16, color: '#333' },
  emptyTitle: {
    fontSize: 24, fontWeight: 600, color: '#1a1a1a', margin: '0 0 8px',
  },
  emptyHint: { fontSize: 14, color: '#888', margin: '0 0 24px' },
  quickActions: { display: 'flex', gap: 12 },
  quickCard: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '10px 18px', background: '#fff', borderRadius: 8,
    border: '1px solid #e0e0e0', cursor: 'pointer',
    boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
  },
  quickIcon: {
    width: 22, height: 22, borderRadius: 6,
    background: '#333',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 13, fontWeight: 600,
  },
  quickText: { fontSize: 13, fontWeight: 500, color: '#333' },
};
