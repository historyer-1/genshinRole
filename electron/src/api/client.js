// ==================== 配置 ====================
// FastAPI 后端服务地址
const BASE_URL = 'http://127.0.0.1:8000';

// ==================== 会话管理接口 ====================

/**
 * 获取所有可用角色列表
 * 调用 GET /api/roles 接口
 *
 * 返回角色名称数组，如 ['刻晴', '甘雨', '胡桃']
 */
export async function fetchRoles() {
  const res = await fetch(`${BASE_URL}/api/roles`);
  const data = await res.json();
  return data.roles;
}

/**
 * 创建新会话
 * 调用 POST /api/sessions 接口，同一用户同一角色只能有一个会话
 *
 * Args:
 *   userId: 用户 ID（用于标识不同用户）
 *   roleName: 角色名称（如"派蒙"、"刻晴"）
 *
 * 返回会话信息 {display_name, ...}
 */
export async function createSession(userId, roleName) {
  const res = await fetch(`${BASE_URL}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, role_name: roleName }),
  });
  return res.json();
}

/**
 * 获取指定会话的完整历史记录
 * 调用 GET /api/sessions/{userId}/{roleName}/history 接口
 *
 * Args:
 *   userId: 用户 ID
 *   roleName: 角色名称
 *
 * 返回消息数组 [{role, content, ...}, ...]
 */
export async function fetchHistory(userId, roleName) {
  const res = await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}/history`);
  const data = await res.json();
  return data.history;
}

/**
 * 分页获取历史记录
 * 调用 GET /api/sessions/{userId}/{roleName}/history/batch 接口
 * 用于向上滚动加载更早的消息
 *
 * Args:
 *   userId: 用户 ID
 *   roleName: 角色名称
 *   limit: 每页条数，默认 10
 *   offset: 偏移量（已加载的消息数），默认 0
 *
 * 返回 {history: [...], ...}
 */
export async function fetchBatchHistory(userId, roleName, limit = 10, offset = 0) {
  const res = await fetch(
    `${BASE_URL}/api/sessions/${userId}/${roleName}/history/batch?limit=${limit}&offset=${offset}`
  );
  return res.json();
}

/**
 * 删除指定会话
 * 调用 DELETE /api/sessions/{userId}/{roleName} 接口
 *
 * Args:
 *   userId: 用户 ID
 *   roleName: 角色名称
 */
export async function deleteSession(userId, roleName) {
  await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}`, { method: 'DELETE' });
}

/**
 * 获取用户的所有会话列表
 * 调用 GET /api/sessions/{userId} 接口
 *
 * Args:
 *   userId: 用户 ID
 *
 * 返回会话数组 [{role_name, display_name}, ...]
 */
export async function fetchUserSessions(userId) {
  const res = await fetch(`${BASE_URL}/api/sessions/${userId}`);
  const data = await res.json();
  return data.sessions;
}

// ==================== 聊天接口 ====================

/**
 * SSE 流式聊天接口
 * 调用 POST /api/sessions/{userId}/{roleName}/chat 接口
 * 通过 Server-Sent Events 逐 token 接收 AI 回复
 *
 * Args:
 *   userId: 用户 ID
 *   roleName: 角色名称
 *   message: 用户发送的消息内容
 *   onToken: 收到单个 token 时的回调，参数为 token 字符串
 *   onDone: 流式完成时的回调，参数为完整回复文本
 *   onError: 请求出错时的回调，参数为错误信息
 *   onAudio: 收到语音合成结果时的回调，参数为 (base64音频, 格式)
 *   voice: 是否启用语音合成，默认 false
 *
 * 返回 AbortController 对象，调用 controller.abort() 可取消请求
 */
export function chatStream(userId, roleName, message, onToken, onDone, onError, onAudio, voice = false) {
  // 创建 AbortController 用于取消请求
  const controller = new AbortController();

  // 使用立即执行异步函数处理流式响应
  (async () => {
    try {
      // 发送 POST 请求到聊天接口
      const res = await fetch(`${BASE_URL}/api/sessions/${userId}/${roleName}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, voice }),
        // 绑定 AbortSignal 以支持取消
        signal: controller.signal,
      });

      // 获取响应流的读取器
      const reader = res.body.getReader();
      // 文本解码器，将二进制数据转为字符串
      const decoder = new TextDecoder();
      // 缓冲区，处理不完整的 SSE 事件
      let buffer = '';
      // 当前事件类型（token/done/audio/voice_error）
      let eventType = '';

      // 逐块读取 SSE 流
      while (true) {
        const { done, value } = await reader.read();
        // 流结束时退出循环
        if (done) break;

        // 将二进制数据解码并追加到缓冲区
        buffer += decoder.decode(value, { stream: true });
        // 按换行符分割，最后一行可能不完整
        const lines = buffer.split('\n');
        // 保留最后一行（可能是不完整的事件）
        buffer = lines.pop();

        // 解析每一行 SSE 数据
        // SSE 格式：event: xxx\ndata: xxx\n\n
        for (const line of lines) {
          if (line.startsWith('event:')) {
            // 事件类型行：提取类型名
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            // 数据行：提取 JSON 字符串并解析
            const jsonStr = line.slice(5).trim();
            try {
              const data = JSON.parse(jsonStr);
              if (eventType === 'token') {
                // 流式 token：调用回调传给上层
                onToken(data.content);
              } else if (eventType === 'done') {
                // 流式结束：传入完整文本
                onDone(data.content);
              } else if (eventType === 'audio' && onAudio) {
                // 语音合成结果：传入 base64 音频和格式
                onAudio(data.audio, data.format);
              } else if (eventType === 'voice_error') {
                // 语音合成失败：打印警告
                console.warn('语音合成失败:', data.detail);
              }
            } catch {
              // JSON 解析失败，忽略该条数据
            }
          }
        }
      }
    } catch (e) {
      // 忽略用户主动取消导致的 AbortError
      if (e.name !== 'AbortError') {
        onError(e.message);
      }
    }
  })();

  // 返回 controller，调用方可通过 controller.abort() 取消请求
  return controller;
}
