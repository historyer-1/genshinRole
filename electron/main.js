const { app, BrowserWindow } = require('electron');
const { spawn, spawnSync } = require('child_process');
const path = require('path');

let fastapiProcess = null;
let viteProcess = null;
let isCleaningUp = false;
const isDev = !app.isPackaged;

function spawnProcess(name, cmd, args, cwd) {
  const proc = spawn(cmd, args, {
    cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    shell: process.platform === 'win32',
  });

  proc.stdout.on('data', (data) => {
    console.log(`[${name}] ${data.toString().trim()}`);
  });

  proc.stderr.on('data', (data) => {
    console.error(`[${name}] ${data.toString().trim()}`);
  });

  proc.on('exit', (code) => {
    console.log(`[${name}] exited with code ${code}`);
  });

  return proc;
}

function startBackend() {
  const rootDir = path.join(__dirname, '..');
  fastapiProcess = spawnProcess(
    'backend', 'python', ['-m', 'server'], rootDir,
  );
}

function startFrontend() {
  viteProcess = spawnProcess(
    'frontend', 'npx', ['vite', '--host', '127.0.0.1', '--port', '5173'], __dirname,
  );
}

function stopProcess(proc) {
  if (proc && !proc.killed) {
    // Windows 上 shell: true 时，kill() 只杀 cmd.exe 壳，子进程（python/npx）会残留。
    // 用 taskkill /T 同步杀掉整个进程树，确保退出前子进程全部终止。
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/pid', String(proc.pid), '/T', '/F'], { shell: true });
    } else {
      proc.kill('SIGTERM');
    }
    // taskkill 是外部操作，proc.killed 不会自动更新，手动标记防止重复清理
    proc.killed = true;
  }
}

function cleanup() {
  if (isCleaningUp) return;
  isCleaningUp = true;
  stopProcess(viteProcess);
  stopProcess(fastapiProcess);
}

async function waitForReady(url, maxRetries = 60, interval = 500) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error(`${url} failed to start`);
}

app.whenReady().then(async () => {
  startBackend();

  try {
    await waitForReady('http://127.0.0.1:8000/health');
  } catch (e) {
    console.error(e.message);
    app.quit();
    return;
  }

  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    startFrontend();
    try {
      await waitForReady('http://127.0.0.1:5173');
    } catch (e) {
      console.error(e.message);
      app.quit();
      return;
    }
    win.loadURL('http://127.0.0.1:5173');
  } else {
    win.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }
});

app.on('window-all-closed', () => {
  cleanup();
  app.quit();
});

app.on('before-quit', () => {
  cleanup();
});
