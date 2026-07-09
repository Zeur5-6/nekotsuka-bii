/**
 * preload スクリプト
 * contextIsolation 環境でレンダラーに公開する API を最小限に絞る
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('biiAPI', {
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  closeWindow: () => ipcRenderer.send('close-window'),
  restoreWindow: () => ipcRenderer.send('restore-window'),
  hideWindow: () => ipcRenderer.send('hide-window'),
  showWindow: () => ipcRenderer.send('show-window'),
  setAlwaysOnTop: (flag) => ipcRenderer.send('set-always-on-top', flag),
  moveWindow: (dx, dy) => ipcRenderer.send('move-window', { mouseX: dx, mouseY: dy }),
  findModel: () => ipcRenderer.invoke('find-model'),
});
