// ==================== 依赖导入 ====================
import { useState, useEffect, useCallback } from 'react';
// API 封装：获取角色列表、用户会话列表、创建会话
import { fetchRoles, fetchUserSessions, createSession } from '../api/client';

// ==================== 会话管理 Hook ====================

/**
 * 会话管理 hook
 * 管理角色列表、用户已开的会话、当前活跃角色和会话创建
 * 是会话管理层，被 App 组件调用，为 useChat 提供会话上下文
 *
 * Args:
 *   userId: 用户 ID（登录后设置，用于加载该用户的会话）
 *
 * 返回包含状态和操作方法的对象
 */
export function useSession(userId) {
  // ==================== 状态定义 ====================
  // 所有可用角色名称列表（从后端 /api/roles 获取）
  const [roles, setRoles] = useState([]);
  // 用户已开启的会话列表 [{role_name: string, display_name: string}, ...]
  const [sessions, setSessions] = useState([]);
  // 当前选中的角色名称（如 '派蒙'、'刻晴'）
  const [activeRole, setActiveRole] = useState(null);
  // 当前角色的显示名称（如 '派蒙'、'玉衡星·刻晴'）
  const [displayName, setDisplayName] = useState('');
  // 会话是否就绪（createSession 完成后设为 true，useChat 依赖此状态）
  const [sessionReady, setSessionReady] = useState(false);

  // ==================== 副作用：加载角色列表 ====================

  // 组件挂载时一次性加载所有可用角色
  // 空依赖数组 [] 表示只在挂载时执行一次
  useEffect(() => {
    fetchRoles().then(setRoles).catch(console.error);
  }, []);

  // ==================== 副作用：加载用户会话 ====================

  // 用户 ID 变化时加载该用户的已有会话列表
  // userId 为空时不加载（未登录状态）
  useEffect(() => {
    if (userId) {
      fetchUserSessions(userId).then(setSessions).catch(console.error);
    }
  }, [userId]);

  // ==================== 打开会话 ====================

  /**
   * 打开（创建或复用）指定角色的会话
   * 调用后端 POST /api/sessions 接口，同一用户同一角色只会有一个会话
   * 创建成功后更新状态，通知 useChat 可以开始聊天
   *
   * Args:
   *   roleName: 角色名称（如 '派蒙'、'刻晴'）
   *
   * 返回会话信息对象 {display_name: string, ...}
   */
  const openSession = useCallback(async (roleName) => {
    if (!userId) return;
    // 先标记会话未就绪（useChat 会等待此状态变为 true）
    setSessionReady(false);
    // 调用后端创建会话
    const info = await createSession(userId, roleName);
    // 更新显示名称
    setDisplayName(info.display_name);
    // 更新当前活跃角色
    setActiveRole(roleName);
    // 将新会话添加到已开会话列表（如果该角色的会话不存在）
    setSessions((prev) => {
      if (prev.some((s) => s.role_name === roleName)) return prev;
      return [...prev, { role_name: roleName, display_name: info.display_name }];
    });
    // 标记会话就绪，触发 useChat 加载历史
    setSessionReady(true);
    return info;
  }, [userId]);

  // ==================== 返回值 ====================
  return {
    roles,              // 所有可用角色列表
    sessions,           // 用户已开的会话列表
    activeRole,         // 当前活跃角色名
    displayName,        // 当前角色显示名
    sessionReady,       // 会话是否就绪
    setActiveRole,      // 设置活跃角色
    setDisplayName,     // 设置显示名称
    openSession,        // 打开会话函数
  };
}
