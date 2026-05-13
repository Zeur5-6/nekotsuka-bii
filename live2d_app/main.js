/**
 * Electronメインプロセス
 * Live2Dモデルをデスクトップ上に常駐表示
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// GPU設定：デフォルト設定を使用し、クラッシュを防ぐ
// クラッシュする場合は以下のいくつかを有効/無効にしてみてください
// app.disableHardwareAcceleration(); // これを有効にすると動作は遅くなりますがクラッシュは直る可能性があります

// Windowsでの安定性向上のためANGLEバックエンドをデフォルトに
app.commandLine.appendSwitch('use-angle', 'default');

// Windowsでの安定性向上のためANGLEバックエンドをD3D11に固定
// app.commandLine.appendSwitch('use-angle', 'd3d11');
// 透明ウィンドウでのクラッシュを防ぐためのフラグ
// app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');

// GPUプロセスがクラッシュするため、ハードウェアアクセラレーションを無効化（安定性優先）
app.disableHardwareAcceleration();

let mainWindow;

function createWindow() {
  // メインウィンドウを作成
  mainWindow = new BrowserWindow({
    width: 400,
    height: 600,
    frame: false,  // フレームレス（タイトルバーなし）
    transparent: true,  // 透明背景
    alwaysOnTop: true,  // 常に最前面
    skipTaskbar: false,  // タスクバーに表示（Alt+Tab認識のため）
    resizable: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true,
      webgl: true,  // WebGLを有効化
      experimentalFeatures: true,  // 実験的機能を有効化
      offscreen: false  // オフスクリーンレンダリングを無効化
    }
  });

  // HTMLファイルを読み込む
  mainWindow.loadFile('index.html');

  // 開発者ツールを開く（デバッグ用、本番では削除可）
  // mainWindow.webContents.openDevTools();

  // ウィンドウが閉じられたとき
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // ドラッグ可能にする
  mainWindow.setIgnoreMouseEvents(false, { forward: true });
}

// アプリの準備ができたらウィンドウを作成
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// すべてのウィンドウが閉じられたとき
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC通信（Pythonバックエンドとの連携用）
ipcMain.on('minimize-window', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.on('close-window', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.on('set-always-on-top', (event, flag) => {
  if (mainWindow) {
    mainWindow.setAlwaysOnTop(flag);
  }
});

ipcMain.on('restore-window', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    // hide()されたウィンドウを戻すため
    mainWindow.show();
    mainWindow.focus();
  }
});

ipcMain.on('hide-window', () => {
  if (mainWindow) {
    mainWindow.hide();
  }
});

ipcMain.on('show-window', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});

// ウィンドウ移動用（レンダラーからの操作）
ipcMain.on('move-window', (event, { mouseX, mouseY }) => {
  if (mainWindow) {
    const { x, y } = mainWindow.getBounds();
    mainWindow.setPosition(x + mouseX, y + mouseY);
  }
});
