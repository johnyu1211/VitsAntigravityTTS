const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
let didSpawnBackend = false;
const SERVER_URL = 'http://127.0.0.1:7861';

process.on('uncaughtException', (err) => {
  console.error('[Electron Uncaught Exception]', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Electron Unhandled Rejection]', reason);
});

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

  req.setTimeout(1000, () => {
    req.destroy();
    callback(false);
  });
}

function startPythonBackend() {
  console.log('[Electron] Starting Python Voice Engine...');
  const pyScript = path.join(__dirname, 'antigravity_tts.py');

  pythonProcess = spawn('python', [pyScript, '--no-browser'], {
    cwd: __dirname,
    shell: true,
    stdio: 'ignore'
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

function checkServerReady(onReady, retries = 60) {
  if (retries <= 0) {
    console.error('[Electron] Healthcheck timeout.');
    return;
  }

  checkPortActive((active) => {
    if (active) {
      console.log('[Electron] Connected to Voice Engine!');
      onReady();
    } else {
      setTimeout(() => checkServerReady(onReady, retries - 1), 400);
    }
  });
}

function createWindow() {
  Menu.setApplicationMenu(null);

  mainWindow = new BrowserWindow({
    width: 780,
    height: 920,
    minWidth: 640,
    minHeight: 700,
    backgroundColor: '#1c1c1e',
    title: 'Antigravity Voice Studio',
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // 1. Load sleek loading splash
  mainWindow.loadFile(path.join(__dirname, 'loading.html')).catch(() => {});

  // 2. Check if already running or launch backend
  checkPortActive((alreadyRunning) => {
    if (alreadyRunning) {
      console.log('[Electron] Existing backend detected on port 7861. Connecting immediately...');
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.loadURL(SERVER_URL).catch(() => {});
      }
    } else {
      startPythonBackend();
      checkServerReady(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.loadURL(SERVER_URL).catch(() => {});
        }
      });
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
