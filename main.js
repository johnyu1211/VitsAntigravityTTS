const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
const SERVER_URL = 'http://127.0.0.1:7861';

function startPythonBackend() {
  console.log('[Electron] Spawning Python Voice Engine backend...');
  
  const pyScript = path.join(__dirname, 'antigravity_tts.py');
  pythonProcess = spawn('python', [pyScript, '--no-browser'], {
    cwd: __dirname,
    stdio: 'pipe'
  });

  if (pythonProcess.stdout) {
    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python Engine] ${data.toString().trim()}`);
    });
  }

  if (pythonProcess.stderr) {
    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data.toString().trim()}`);
    });
  }

  pythonProcess.on('error', (err) => {
    console.error('[Electron] Failed to spawn Python process:', err);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`[Electron] Python process exited with code ${code}, signal ${signal}`);
  });
}

function checkServerReady(onReady, retries = 60) {
  if (retries <= 0) {
    console.error('[Electron] Server health check timed out.');
    return;
  }

  http.get(`${SERVER_URL}/api/status`, (res) => {
    if (res.statusCode === 200) {
      console.log('[Electron] Python Voice Engine is healthy and ready!');
      onReady();
    } else {
      setTimeout(() => checkServerReady(onReady, retries - 1), 400);
    }
  }).on('error', () => {
    setTimeout(() => checkServerReady(onReady, retries - 1), 400);
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

  // 1. Show immediate dark loading animation
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));

  // 2. Poll backend and load full UI once ready
  checkServerReady(() => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadURL(SERVER_URL);
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function killPythonBackend() {
  if (pythonProcess && pythonProcess.pid) {
    console.log(`[Electron] Terminating Python process tree (PID: ${pythonProcess.pid})...`);
    try {
      if (process.platform === 'win32') {
        exec(`taskkill /pid ${pythonProcess.pid} /T /F`);
      } else {
        pythonProcess.kill('SIGKILL');
      }
    } catch (e) {
      console.error('[Electron] Error killing python process:', e);
    }
    pythonProcess = null;
  }
}

app.whenReady().then(() => {
  createWindow();
  startPythonBackend();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  killPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killPythonBackend();
});
