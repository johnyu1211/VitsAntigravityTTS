const { app, BrowserWindow, Menu, ipcMain, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
let didSpawnBackend = false;
let isConnected = false;
const SERVER_URL = 'http://127.0.0.1:7861';

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

process.on('uncaughtException', (err) => {
  console.error('[Electron Uncaught Exception]', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Electron Unhandled Rejection]', reason);
});

function getPythonExecutable() {
  const localPy = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe');
  if (fs.existsSync(localPy)) return localPy;
  return 'python';
}

function checkPortActive(callback) {
  const req = http.get(`${SERVER_URL}/api/status`, (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else {
      callback(false);
    }
  });

  req.on('error', () => {
    callback(false);
  });

  req.setTimeout(800, () => {
    req.destroy();
    callback(false);
  });
}

function startPythonBackend() {
  console.log('[Electron] Starting Python Voice Engine in background...');
  const rootDir = path.resolve(__dirname, '..');
  const pyExe = getPythonExecutable();
  const pyScript = path.join(rootDir, 'antigravity_tts.py');
  const logsDir = path.join(rootDir, 'logs');
  if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });
  const logPath = path.join(logsDir, 'electron_backend.log');
  
  let outStream;
  try {
    outStream = fs.openSync(logPath, 'a');
  } catch (e) {
    outStream = 'ignore';
  }

  pythonProcess = spawn(pyExe, ['-u', pyScript, '--no-browser'], {
    cwd: rootDir,
    windowsHide: true,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', outStream, outStream]
  });

  didSpawnBackend = true;

  pythonProcess.on('error', (err) => {
    console.error('[Electron] Python spawn error:', err);
  });

  pythonProcess.on('exit', (code) => {
    console.log(`[Electron] Python backend exited (code: ${code})`);
    pythonProcess = null;
  });
}

function pollAndLoadApp() {
  if (isConnected || !mainWindow || mainWindow.isDestroyed()) return;

  checkPortActive((active) => {
    if (active) {
      console.log('[Electron] Voice Engine is READY! Loading studio GUI...');
      isConnected = true;
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.loadURL(SERVER_URL);
      }
    } else {
      setTimeout(pollAndLoadApp, 400);
    }
  });
}

app.commandLine.appendSwitch('disable-http-cache');

function createWindow() {
  Menu.setApplicationMenu(null);

  const rootDir = path.resolve(__dirname, '..');

  mainWindow = new BrowserWindow({
    width: 1360,
    height: 920,
    minWidth: 980,
    minHeight: 650,
    backgroundColor: '#1c1c1e',
    title: 'Antigravity Voice Studio',
    icon: path.join(__dirname, 'assets', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false
    }
  });

  // Clear session cache immediately so fresh files are always loaded
  try {
    mainWindow.webContents.session.clearCache();
  } catch (e) {}

  // 1. Show main studio UI immediately (Zero waiting time!)
  mainWindow.loadFile(path.join(rootDir, 'views', 'index.html')).catch(() => {});

  // 2. Prevent blank screen if load ever fails
  mainWindow.webContents.on('did-fail-load', (event, errorCode) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadFile(path.join(rootDir, 'views', 'index.html')).catch(() => {});
    }
  });

  // 3. Check if backend is running or launch
  checkPortActive((alreadyRunning) => {
    if (!alreadyRunning) {
      startPythonBackend();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function cleanupProcesses() {
  if (didSpawnBackend && pythonProcess && pythonProcess.pid) {
    console.log(`[Electron] Cleaning up spawned backend (PID: ${pythonProcess.pid})...`);
    try {
      if (process.platform === 'win32') {
        exec(`taskkill /pid ${pythonProcess.pid} /T /F`, () => {});
      } else {
        pythonProcess.kill('SIGKILL');
      }
    } catch (e) {}
    pythonProcess = null;
  }
}

app.whenReady().then(() => {
  createWindow();

  ipcMain.on('app-relaunch', () => {
    console.log('[Electron] Relaunching application...');
    cleanupProcesses();
    app.relaunch();
    app.exit(0);
  });

  ipcMain.on('app-reload', () => {
    console.log('[Electron] Reloading window...');
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.reload();
    }
  });

  ipcMain.handle('get-clipboard-image', async () => {
    try {
      // 1. Raw image / screenshot / web-copied image
      const img = clipboard.readImage();
      if (!img.isEmpty()) {
        return { type: 'data', data: img.toDataURL() };
      }

      // 2. Copied image file from Windows Explorer (e.g. Ctrl+C on an image file in folder)
      try {
        const rawPath = clipboard.read('FileNameW') || clipboard.read('FileName') || clipboard.readText();
        if (rawPath) {
          const cleanPath = rawPath.replace(/\0/g, '').trim().replace(/^"|"$/g, '');
          if (fs.existsSync(cleanPath) && /\.(png|jpe?g|webp|bmp|gif)$/i.test(cleanPath)) {
            const fileBuf = fs.readFileSync(cleanPath);
            const ext = path.extname(cleanPath).toLowerCase();
            const mime = ext === '.png' ? 'image/png' : ext === '.webp' ? 'image/webp' : 'image/jpeg';
            return { type: 'data', data: `data:${mime};base64,${fileBuf.toString('base64')}` };
          }
        }
      } catch (e) {}

      // 3. Web URL or Base64 string copied to clipboard
      const text = clipboard.readText().trim();
      if (text && (text.startsWith('http://') || text.startsWith('https://') || text.startsWith('data:image/'))) {
        return { type: 'url', data: text };
      }
    } catch (err) {
      console.error('[Electron Clipboard Read Error]', err);
    }
    return null;
  });

  ipcMain.on('app-relaunch', () => {
    cleanupProcesses();
    app.relaunch();
    app.exit(0);
  });

  ipcMain.on('app-reload', () => {
    if (mainWindow) {
      mainWindow.reload();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  cleanupProcesses();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  cleanupProcesses();
});
