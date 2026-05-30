// ==================== 依赖导入 ====================
// Electron 核心模块：app 控制应用生命周期，BrowserWindow 创建窗口
const { app, BrowserWindow } = require('electron');
// 子进程模块：spawn 异步启动进程，spawnSync 同步执行命令
const { spawn, spawnSync } = require('child_process');
// 路径处理模块
const path = require('path');

// ==================== 全局状态 ====================
// 后端（FastAPI）子进程引用，用于启动和关闭时管理
let fastapiProcess = null;
// 前端（Vite）子进程引用，仅开发模式使用
let viteProcess = null;
// 防止重复清理的标志，避免 cleanup() 被多次调用
let isCleaningUp = false;
// 是否为开发模式（未打包时为 true，打包后为 false）
const isDev = !app.isPackaged;

/**
 * 启动子进程并绑定日志输出
 * 将子进程的 stdout 和 stderr 转发到主进程控制台，方便调试
 *
 * Args:
 *   name: 进程名称，用作日志前缀（如 'backend'、'frontend'）
 *   cmd: 要执行的命令（如 'python'、'npx'）
 *   args: 命令参数数组（如 ['-m', 'server']）
 *   cwd: 子进程的工作目录
 */
function spawnProcess(name, cmd, args, cwd) {
  // 创建子进程，Windows 下需要 shell: true 才能正确解析命令
  const proc = spawn(cmd, args, {
    cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
  });

  // 将子进程的标准输出转发到主进程控制台，每行前缀加进程名
  proc.stdout.on('data', (data) => {
    console.log(`[${name}] ${data.toString().trim()}`);
  });

  // 将子进程的错误输出转发到主进程控制台
  proc.stderr.on('data', (data) => {
    console.error(`[${name}] ${data.toString().trim()}`);
  });

  // 子进程退出时打印退出码
  proc.on('exit', (code) => {
    console.log(`[${name}] exited with code ${code}`);
  });

  return proc;
}

/**
 * 启动 FastAPI 后端服务
 * 工作目录设为项目根目录（electron 的上级目录），执行 python -m server
 */
function startBackend() {
  const rootDir = path.join(__dirname, '..');
  fastapiProcess = spawnProcess(
    'backend', 'python', ['-m', 'server'], rootDir,
  );
}

/**
 * 启动 Vite 前端开发服务器
 * 绑定 127.0.0.1:5173，仅在开发模式下调用
 */
function startFrontend() {
  viteProcess = spawnProcess(
    'frontend', 'npx', ['vite', '--host', '127.0.0.1', '--port', '5173'], __dirname,
  );
}

/**
 * 安全终止子进程
 * Windows 下 shell: true 时，Node 的 kill() 只杀 cmd.exe 壳，子进程会残留，
 * 所以用 taskkill /T 杀掉整个进程树。
 *
 * Args:
 *   proc: 要终止的子进程对象
 */
function stopProcess(proc) {
  // 检查进程存在且未被标记为已杀死
  if (proc && !proc.killed) {
    if (process.platform === 'win32') {
      // Windows：用 taskkill /T（杀进程树）/F（强制）终止
      spawnSync('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { shell: true });
    } else {
      // macOS/Linux：直接发送 SIGTERM 信号
      proc.kill('SIGTERM');
    }
    // taskkill 是外部操作，proc.killed 不会自动更新，手动标记防止重复清理
    proc.killed = true;
  }
}

/**
 * 清理所有子进程
 * 按顺序终止 Vite 和 FastAPI，防止端口残留
 * 通过 isCleaningUp 标志防止重复执行
 */
function cleanup() {
  if (isCleaningUp) return;
  isCleaningUp = true;
  stopProcess(viteProcess);
  stopProcess(fastapiProcess);
}

/**
 * 轮询等待服务就绪
 * 定期向指定 URL 发送请求，直到返回 200 或超过最大重试次数
 *
 * Args:
 *   url: 健康检查地址（如 'http://127.0.0.1:8000/health'）
 *   maxRetries: 最大重试次数，默认 60 次
 *   interval: 重试间隔（毫秒），默认 500ms
 */
async function waitForReady(url, maxRetries = 60, interval = 500) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      // HTTP 2xx 表示服务就绪
      if (res.ok) return;
    } catch {
      // 网络错误（连接被拒绝等）忽略，继续重试
    }
    // 等待指定间隔后重试
    await new Promise((r) => setTimeout(r, interval));
  }
  // 超过最大重试次数，抛出错误
  throw new Error(`${url} failed to start`);
}

// ==================== 应用启动流程 ====================
// Electron 应用就绪后执行的主逻辑
app.whenReady().then(async () => {
  // 第一步：启动后端服务
  startBackend();

  // 第二步：等待后端健康检查通过
  try {
    await waitForReady('http://127.0.0.1:8000/health');
  } catch (e) {
    // 后端启动失败，退出应用
    console.error(e.message);
    app.quit();
    return;
  }

  // 第三步：创建 Electron 窗口
  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      // 禁止渲染进程直接访问 Node API（安全考虑）
      nodeIntegration: false,
      // 启用上下文隔离，主进程和渲染进程互相独立
      contextIsolation: true,
    },
  });

  // 第四步：根据模式加载前端页面
  if (isDev) {
    // 开发模式：启动 Vite 开发服务器
    startFrontend();
    try {
      // 等待 Vite 服务就绪
      await waitForReady('http://127.0.0.1:5173');
    } catch (e) {
      console.error(e.message);
      app.quit();
      return;
    }
    // 加载 Vite 开发服务器的 URL（支持热更新）
    win.loadURL('http://127.0.0.1:5173');
  } else {
    // 生产模式：加载打包后的静态文件
    win.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }
});

// ==================== 应用退出处理 ====================
// 所有窗口关闭时：清理子进程并退出应用
app.on('window-all-closed', () => {
  cleanup();
  app.quit();
});

// 应用即将退出时：确保子进程被清理（兜底处理）
app.on('before-quit', () => {
  cleanup();
});
