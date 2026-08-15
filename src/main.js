const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
let didSpawnBackend = false;
let isConnected = false;
const SERVER_URL = 'http://127.0.0.1:7861';

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

function createWindow() {
  Menu.setApplicationMenu(null);

  const rootDir = path.resolve(__dirname, '..');

  mainWindow = new BrowserWindow({
    width: 780,
    height: 920,
    minWidth: 640,
    minHeight: 700,
    backgroundColor: '#1c1c1e',
    title: 'Antigravity Voice Studio',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // 1. Show sleek loading screen first
  mainWindow.loadFile(path.join(rootDir, 'views', 'loading.html')).catch(() => {});

  // 2. Prevent blank screen if load ever fails
  mainWindow.webContents.on('did-fail-load', (event, errorCode) => {
    if (!isConnected && mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadFile(path.join(rootDir, 'views', 'loading.html')).catch(() => {});
      setTimeout(pollAndLoadApp, 600);
    }
  });

  // 3. Check if already running or launch
  checkPortActive((alreadyRunning) => {
    if (alreadyRunning) {
      console.log('[Electron] Existing backend detected. Connecting immediately...');
      isConnected = true;
      mainWindow.loadURL(SERVER_URL);
    } else {
      startPythonBackend();
      pollAndLoadApp();
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
