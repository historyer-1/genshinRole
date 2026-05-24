export default function RoleSelector({ roles, sessions, activeRole, onSelectRole, onSwitchSession }) {
  return (
    <div style={{ width: 200, borderRight: '1px solid #ddd', overflowY: 'auto', padding: 12 }}>
      <div style={{ fontWeight: 'bold', marginBottom: 8 }}>角色列表</div>

      {sessions.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>已开启会话</div>
          {sessions.map((s) => (
            <div
              key={s.role_name}
              onClick={() => onSwitchSession(s.role_name, s.display_name)}
              style={{
                padding: '4px 8px',
                cursor: 'pointer',
                borderRadius: 4,
                marginBottom: 2,
                background: activeRole === s.role_name ? '#e3f2fd' : 'transparent',
              }}
            >
              {s.display_name || s.role_name}
            </div>
          ))}
          <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #eee' }} />
        </div>
      )}

      <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>全部角色</div>

      <div
        onClick={() => onSelectRole('派蒙')}
        style={{
          padding: '4px 8px',
          cursor: 'pointer',
          borderRadius: 4,
          marginBottom: 2,
          background: activeRole === '派蒙' ? '#e3f2fd' : 'transparent',
        }}
      >
        派蒙
      </div>

      {roles.map((r) => (
        <div
          key={r}
          onClick={() => onSelectRole(r)}
          style={{
            padding: '4px 8px',
            cursor: 'pointer',
            borderRadius: 4,
            marginBottom: 2,
            background: activeRole === r ? '#e3f2fd' : 'transparent',
          }}
        >
          {r}
        </div>
      ))}
    </div>
  );
}
