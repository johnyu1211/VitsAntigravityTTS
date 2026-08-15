const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  relaunch: () => ipcRenderer.send('app-relaunch'),
  reload: () => ipcRenderer.send('app-reload'),
  getClipboardImage: () => ipcRenderer.invoke('get-clipboard-image')
});
