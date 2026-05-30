/**
 * 角色选择侧栏组件
 * 显示已开启的会话列表，底部提供新建会话按钮
 * 采用接近白色的磨砂半透明效果
 *
 * Args:
 *   sessions: 用户已开启的会话列表 [{role_name, display_name}, ...]
 *   activeRole: 当前选中的角色名称
 *   onSwitchSession: 切换会话的回调，参数为 (角色名称, 显示名称)
 *   onNewSession: 点击新建按钮的回调
 */
export default function RoleSelector({ sessions, activeRole, onSwitchSession, onNewSession }) {
  return (
    <div style={styles.sidebar}>
      {/* 应用标题 */}
      <div style={styles.header}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>✦</div>
          <span style={styles.logoText}>原神角色扮演</span>
        </div>
      </div>

      {/* 新建按钮 */}
      <div style={styles.newBtnWrapper}>
        <button style={styles.newBtn} onClick={onNewSession}>
          <span style={styles.newBtnIcon}>+</span>
          <span style={styles.newBtnText}>新建会话</span>
        </button>
      </div>

      {/* 会话列表 */}
      <div style={styles.sessionList}>
        {sessions.length === 0 ? (
          <div style={styles.empty}>暂无会话</div>
        ) : (
          sessions.map((s) => {
            const isActive = activeRole === s.role_name;
            return (
              <div
                key={s.role_name}
                style={{ ...styles.sessionItem, ...(isActive ? styles.sessionItemActive : {}) }}
                onClick={() => onSwitchSession(s.role_name, s.display_name)}
              >
                <div style={styles.avatar}>
                  {(s.display_name || s.role_name)[0]}
                </div>
                <div style={styles.sessionInfo}>
                  <div style={styles.sessionName}>{s.display_name || s.role_name}</div>
                  <div style={styles.sessionRole}>{s.role_name}</div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 底部用户信息 */}
      <div style={styles.footer}>
        <div style={styles.footerIcon}>👤</div>
        <span style={styles.footerText}>当前用户</span>
      </div>
    </div>
  );
}

const styles = {
  sidebar: {
    width: 260, height: '100vh',
    background: 'rgba(245, 245, 245, 0.7)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    borderRight: '1px solid rgba(0,0,0,0.06)',
    display: 'flex', flexDirection: 'column',
  },
  header: {
    padding: '20px 16px', borderBottom: '1px solid rgba(0,0,0,0.06)',
  },
  logo: { display: 'flex', alignItems: 'center', gap: 10 },
  logoIcon: {
    width: 28, height: 28, borderRadius: 6,
    background: '#333',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 12, color: '#fff', fontWeight: 700,
  },
  logoText: { fontSize: 14, fontWeight: 600, color: '#1a1a1a' },

  newBtnWrapper: { padding: '16px 12px 8px' },
  newBtn: {
    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
    gap: 8, padding: '10px 0', border: '1px dashed #ccc',
    borderRadius: 8, background: 'rgba(255,255,255,0.5)',
    cursor: 'pointer', transition: 'all 0.2s',
  },
  newBtnIcon: {
    width: 18, height: 18, borderRadius: 4,
    background: '#333',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontSize: 12, fontWeight: 600,
  },
  newBtnText: { fontSize: 12, color: '#666' },

  sessionList: { flex: 1, overflowY: 'auto', padding: '8px 8px' },
  empty: {
    textAlign: 'center', color: '#aaa', padding: '40px 16px', fontSize: 12,
  },
  sessionItem: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
    marginBottom: 2, transition: 'all 0.15s',
  },
  sessionItemActive: {
    background: 'rgba(0,0,0,0.06)',
  },
  avatar: {
    width: 32, height: 32, borderRadius: '50%',
    background: '#e0e0e0',
    color: '#333', display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 13, fontWeight: 600, flexShrink: 0,
  },
  sessionInfo: { flex: 1, minWidth: 0 },
  sessionName: {
    fontSize: 13, fontWeight: 500, color: '#1a1a1a',
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  },
  sessionRole: { fontSize: 11, color: '#999', marginTop: 2 },

  footer: {
    padding: '14px 16px', borderTop: '1px solid rgba(0,0,0,0.06)',
    display: 'flex', alignItems: 'center', gap: 10,
  },
  footerIcon: {
    width: 28, height: 28, borderRadius: 6, background: 'rgba(0,0,0,0.05)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12,
  },
  footerText: { fontSize: 12, color: '#888' },
};
