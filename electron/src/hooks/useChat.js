// ==================== 依赖导入 ====================
import { useState, useRef, useCallback, useEffect } from 'react';
// API 封装：SSE 流式聊天和分页历史加载
import { chatStream, fetchBatchHistory } from '../api/client';

// ==================== 常量 ====================
// 每次加载历史记录的条数
const LOAD_LIMIT = 10;

// ==================== 工具函数 ====================

/**
 * 按中文标点和换行符拆分句子
 * 用于语音播放时的打字机同步效果：根据每个句子的字数比例分配显示时间
 *
 * Args:
 *   text: 要拆分的完整文本
 *
 * 返回句子数组，每个元素包含句子内容和结尾标点
 */
function splitSentences(text) {
  // 用正则按中文句号、感叹号、问号、省略号和换行符拆分
  // 括号捕获分隔符，使其保留在结果数组中
  const parts = text.split(/([。！？…\n]+)/);
  const result = [];
  // 将文本和标点重新组合（奇数位是标点，偶数位是文本）
  for (let i = 0; i < parts.length; i += 2) {
    result.push(parts[i] + (parts[i + 1] || ''));
  }
  // 过滤掉空字符串
  return result.filter((s) => s.length > 0);
}

// ==================== 聊天逻辑 Hook ====================

/**
 * 聊天逻辑 hook
 * 管理消息列表、流式输出、语音播放和历史加载
 * 是聊天功能的核心逻辑层，被 App 组件调用
 *
 * Args:
 *   userId: 用户 ID
 *   roleName: 当前角色名称
 *   sessionReady: 会话是否就绪（useSession 中创建完成后为 true）
 *
 * 返回包含状态和操作方法的对象
 */
export function useChat(userId, roleName, sessionReady) {
  // ==================== 状态定义 ====================
  // 消息列表：[{role: 'user'|'assistant', content: string, audioUrl?: string}, ...]
  const [messages, setMessages] = useState([]);
  // 当前流式输出的文本（为空字符串表示无流式输出）
  const [streaming, setStreaming] = useState('');
  // 是否正在流式输出（控制发送/停止按钮切换）
  const [isStreaming, setIsStreaming] = useState(false);
  // 是否正在加载历史记录（控制加载提示显示）
  const [loadingHistory, setLoadingHistory] = useState(false);
  // 是否还有更早的历史记录可加载
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  // 是否启用语音合成（由用户通过按钮切换）
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  // ==================== Refs ====================
  // SSE 请求的 AbortController 引用，用于取消正在进行的请求
  const controllerRef = useRef(null);
  // 历史记录的偏移量，分页加载时记录已加载数量
  const offsetRef = useRef(0);
  // 语音模式下等待语音合成完成的完整文本
  const pendingTextRef = useRef(null);
  // 打字机效果的 setTimeout 定时器 ID，用于停止时清理
  const typewriterTimerRef = useRef(null);

  // ==================== 副作用：自动加载历史 ====================

  // 会话就绪后自动加载最近的历史记录
  // 依赖 [userId, roleName, sessionReady]，任一变化时重新加载
  useEffect(() => {
    // 三个条件都满足才加载
    if (!userId || !roleName || !sessionReady) return;
    setLoadingHistory(true);
    // 重置偏移量
    offsetRef.current = 0;
    fetchBatchHistory(userId, roleName, LOAD_LIMIT, 0)
      .then((data) => {
        const history = data.history || [];
        // 设置消息列表
        setMessages(history);
        // 更新偏移量
        offsetRef.current = history.length;
        // 如果返回的条数等于请求数，说明可能还有更多
        setHasMoreHistory(history.length >= LOAD_LIMIT);
      })
      .catch((e) => console.error('加载历史记录失败:', e))
      .finally(() => setLoadingHistory(false));
  }, [userId, roleName, sessionReady]);

  // ==================== 副作用：切换角色清空消息 ====================

  // 当 roleName 变为 null（退出会话）时清空消息列表
  useEffect(() => {
    if (!roleName) {
      setMessages([]);
      setHasMoreHistory(true);
      offsetRef.current = 0;
    }
  }, [roleName]);

  // ==================== 发送消息 ====================

  /**
   * 发送消息并启动流式接收
   * 将用户消息添加到列表，然后通过 SSE 流式接收 AI 回复
   *
   * Args:
   *   text: 要发送的消息文本
   */
  const sendMessage = useCallback((text) => {
    // 防止无效调用
    if (!userId || !roleName || isStreaming) return;

    // 清理上一次的打字机效果（如果有）
    if (typewriterTimerRef.current) {
      clearTimeout(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    pendingTextRef.current = null;

    // 将用户消息添加到消息列表
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    // 清空流式文本，开始新的流式输出
    setStreaming('');
    setIsStreaming(true);

    // 累积的完整文本（用于非语音模式）
    let accumulated = '';

    // 调用 SSE 流式聊天接口
    controllerRef.current = chatStream(
      userId,
      roleName,
      text,
      // ==================== onToken 回调：收到单个 token ====================
      (token) => {
        accumulated += token;
        // 非语音模式下实时显示流式文本
        if (!voiceEnabled) {
          setStreaming(accumulated);
        }
        // 语音模式下不显示中间状态，等待语音合成完成
      },
      // ==================== onDone 回调：流式完成 ====================
      (fullText) => {
        if (voiceEnabled) {
          // 语音模式：保存完整文本，等待 onAudio 回调
          pendingTextRef.current = fullText;
          setStreaming('语音生成中...');
        } else {
          // 非语音模式：直接将完整回复添加到消息列表
          setMessages((prev) => [...prev, { role: 'assistant', content: fullText }]);
          setStreaming('');
          setIsStreaming(false);
          controllerRef.current = null;
        }
      },
      // ==================== onError 回调：请求出错 ====================
      (err) => {
        pendingTextRef.current = null;
        // 将错误信息显示为助手消息
        setMessages((prev) => [...prev, { role: 'assistant', content: `[错误] ${err}` }]);
        setStreaming('');
        setIsStreaming(false);
        controllerRef.current = null;
      },
      // ==================== onAudio 回调：收到语音合成结果 ====================
      (audioB64, format) => {
        // 获取之前保存的完整文本
        const text = pendingTextRef.current;
        if (!text) return;
        pendingTextRef.current = null;

        // 将 base64 编码的音频数据解码为二进制
        const audioBytes = Uint8Array.from(atob(audioB64), (c) => c.charCodeAt(0));
        // 创建 Blob 对象（音频文件）
        const blob = new Blob([audioBytes], { type: `audio/${format}` });
        // 创建可播放的 URL
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);

        // 音频元数据加载完成后启动打字机效果
        // 使用 loadedmetadata 而非 canplay，因为需要获取 duration
        audio.addEventListener('loadedmetadata', () => {
          const duration = audio.duration;
          // 将文本拆分为句子
          const sentences = splitSentences(text);
          const totalChars = text.length;

          // 开始播放音频
          audio.play();

          // 打字机效果状态
          let idx = 0;           // 当前句子索引
          let revealed = '';     // 已显示的文本

          /** 显示下一个句子，递归调用直到所有句子显示完毕 */
          const revealNext = () => {
            if (idx >= sentences.length) {
              // 所有句子显示完毕：将最终消息添加到列表
              setMessages((prev) => [...prev, { role: 'assistant', content: text, audioUrl: url }]);
              setStreaming('');
              setIsStreaming(false);
              controllerRef.current = null;
              typewriterTimerRef.current = null;
              return;
            }
            // 累加当前句子到已显示文本
            revealed += sentences[idx];
            setStreaming(revealed);
            // 根据当前句子字数占总字数的比例计算延迟
            // 这样打字机效果能与音频播放大致同步
            const delay = (sentences[idx].length / totalChars) * duration * 1000;
            idx++;
            // 设置定时器显示下一句
            typewriterTimerRef.current = setTimeout(revealNext, delay);
          };

          // 显示第一句并启动定时器链
          setStreaming(sentences[0]);
          idx = 1;
          const firstDelay = (sentences[0].length / totalChars) * duration * 1000;
          typewriterTimerRef.current = setTimeout(revealNext, firstDelay);
        });

        // 预播放（某些浏览器需要用户交互后才能播放，这里静默处理失败）
        audio.play().catch(() => {});
      },
      // 传递语音开关状态
      voiceEnabled
    );
  }, [userId, roleName, isStreaming, voiceEnabled]);

  // ==================== 停止流式输出 ====================

  /**
   * 停止当前的流式输出
   * 清理定时器、中止请求、保存已接收的内容
   */
  const stopStreaming = useCallback(() => {
    // 清除打字机定时器
    if (typewriterTimerRef.current) {
      clearTimeout(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    // 中止 SSE 请求
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    // 将已接收的内容保存到消息列表
    if (pendingTextRef.current) {
      // 有等待语音的完整文本
      setMessages((prev) => [...prev, { role: 'assistant', content: pendingTextRef.current }]);
      pendingTextRef.current = null;
    } else if (streaming && streaming !== '语音生成中...') {
      // 有流式输出的文本（排除语音生成中的占位文字）
      setMessages((prev) => [...prev, { role: 'assistant', content: streaming }]);
    }
    // 重置流式状态
    setStreaming('');
    setIsStreaming(false);
  }, [streaming]);

  // ==================== 加载更多历史 ====================

  /**
   * 加载更早的历史记录
   * 由 ChatWindow 组件在滚动到顶部时触发
   */
  const loadMoreHistory = useCallback(async () => {
    // 防止重复加载或无更多历史时触发
    if (!userId || !roleName || loadingHistory || !hasMoreHistory) return;
    setLoadingHistory(true);
    try {
      // 使用当前偏移量加载更早的记录
      const data = await fetchBatchHistory(userId, roleName, LOAD_LIMIT, offsetRef.current);
      const older = data.history || [];
      // 将更早的记录插入到消息列表前面
      setMessages((prev) => [...older, ...prev]);
      // 更新偏移量
      offsetRef.current += older.length;
      // 判断是否还有更多
      setHasMoreHistory(older.length >= LOAD_LIMIT);
    } catch (e) {
      console.error('加载更多历史记录失败:', e);
    } finally {
      setLoadingHistory(false);
    }
  }, [userId, roleName, loadingHistory, hasMoreHistory]);

  // ==================== 返回值 ====================
  return {
    messages,           // 消息列表
    setMessages,        // 设置消息列表（外部一般不需要使用）
    streaming,          // 当前流式输出文本
    isStreaming,        // 是否正在流式输出
    sendMessage,        // 发送消息函数
    stopStreaming,      // 停止流式输出函数
    loadingHistory,     // 是否正在加载历史
    hasMoreHistory,     // 是否还有更多历史
    loadMoreHistory,    // 加载更多历史函数
    voiceEnabled,       // 语音合成开关
    setVoiceEnabled,    // 设置语音开关
  };
}
