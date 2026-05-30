import { useState, useMemo } from 'react';

/**
 * 新建会话对话框
 * 弹出模态框，提供角色搜索、选择和声音开关
 *
 * Args:
 *   roles: 所有可用角色名称数组
 *   existingRoles: 已创建会话的角色名称数组（用于禁用）
 *   onConfirm: 点击确认的回调，参数为 {roleName, voiceEnabled}
 *   onClose: 关闭对话框的回调
 */
export default function NewSessionDialog({ roles, existingRoles, onConfirm, onClose }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [voice, setVoice] = useState(false);

  // 过滤角色列表
  const filtered = useMemo(() => {
    if (!search.trim()) return roles;
    return roles.filter((r) => r.includes(search.trim()));
  }, [roles, search]);

  // 派蒙固定在顶部
  const sorted = useMemo(() => {
    const others = filtered.filter((r) => r !== '派蒙');
    return filtered.includes('派蒙') ? ['派蒙', ...others] : others;
  }, [filtered]);

  const handleConfirm = () => {
    if (selected) onConfirm({ roleName: selected, voiceEnabled: voice });
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.dialog} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div style={styles.header}>
          <span style={styles.title}>新建会话</span>
          <button style={styles.closeBtn} onClick={onClose}>×</button>
        </div>

        {/* 搜索框 */}
        <input
          style={styles.search}
          placeholder="搜索角色..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />

        {/* 角色列表 */}
        <div style={styles.roleList}>
          {sorted.map((r) => {
            const disabled = existingRoles.includes(r);
            const isSelected = selected === r;
            return (
              <div
                key={r}
                style={{
                  ...styles.roleItem,
                  ...(isSelected ? styles.roleItemSelected : {}),
                  ...(disabled ? styles.roleItemDisabled : {}),
                }}
                onClick={() => !disabled && setSelected(r)}
              >
                <span style={styles.roleName}>{r}</span>
                {disabled && <span style={styles.badge}>已创建</span>}
              </div>
            );
          })}
          {sorted.length === 0 && (
            <div style={styles.empty}>未找到匹配角色</div>
          )}
        </div>

        {/* 声音开关 */}
        <div style={styles.voiceRow}>
          <span style={styles.voiceLabel}>启用语音</span>
          <div
            style={{ ...styles.toggle, ...(voice ? styles.toggleOn : {}) }}
            onClick={() => setVoice(!voice)}
          >
            <div style={{ ...styles.toggleDot, ...(voice ? styles.toggleDotOn : {}) }} />
          </div>
        </div>

        {/* 底部按钮 */}
        <div style={styles.footer}>
          <button style={styles.cancelBtn} onClick={onClose}>取消</button>
          <button
            style={{ ...styles.confirmBtn, ...(selected ? {} : styles.confirmBtnDisabled) }}
            onClick={handleConfirm}
            disabled={!selected}
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  },
  dialog: {
    width: 380, maxHeight: '80vh', background: '#fff', borderRadius: 12,
    boxShadow: '0 8px 32px rgba(0,0,0,0.12)', display: 'flex', flexDirection: 'column',
    overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '20px 20px 0',
  },
  title: { fontSize: 16, fontWeight: 600, color: '#1a1a1a' },
  closeBtn: {
    background: 'none', border: 'none', fontSize: 20, color: '#999',
    cursor: 'pointer', padding: '0 4px', lineHeight: 1,
  },
  search: {
    margin: '16px 20px 0', padding: '10px 14px', fontSize: 14,
    border: '1px solid #e0e0e0', borderRadius: 8, outline: 'none',
    background: '#fafafa',
  },
  roleList: {
    margin: '12px 20px 0', flex: 1, overflowY: 'auto', maxHeight: 320,
  },
  roleItem: {
    padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 4, transition: 'all 0.15s',
  },
  roleItemSelected: {
    background: '#f0f0f0',
  },
  roleItemDisabled: {
    opacity: 0.5, cursor: 'not-allowed',
  },
  roleName: { fontSize: 14, color: '#1a1a1a' },
  badge: {
    fontSize: 11, color: '#888', background: '#f0f0f0',
    padding: '2px 8px', borderRadius: 4,
  },
  empty: {
    textAlign: 'center', color: '#999', padding: 20, fontSize: 13,
  },
  voiceRow: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderTop: '1px solid #f0f0f0',
  },
  voiceLabel: { fontSize: 14, color: '#333' },
  toggle: {
    width: 44, height: 24, borderRadius: 12, background: '#ddd',
    cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
  },
  toggleOn: { background: '#333' },
  toggleDot: {
    width: 20, height: 20, borderRadius: '50%', background: '#fff',
    position: 'absolute', top: 2, left: 2, transition: 'transform 0.2s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
  },
  toggleDotOn: { transform: 'translateX(20px)' },
  footer: {
    display: 'flex', justifyContent: 'flex-end', gap: 10,
    padding: '16px 20px', borderTop: '1px solid #f0f0f0',
  },
  cancelBtn: {
    padding: '8px 20px', fontSize: 13, border: '1px solid #ddd',
    borderRadius: 8, background: '#fff', cursor: 'pointer', color: '#666',
  },
  confirmBtn: {
    padding: '8px 20px', fontSize: 13, border: 'none',
    borderRadius: 8, background: '#333', color: '#fff', cursor: 'pointer',
    fontWeight: 500,
  },
  confirmBtnDisabled: {
    background: '#ccc', cursor: 'not-allowed',
  },
};
