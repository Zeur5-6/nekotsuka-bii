/**
 * Electronメインプロセス
 * Live2Dモデルをデスクトップ上に常駐表示
 *
 * レンダラーは contextIsolation で分離し、必要な操作だけを
 * preload.js の contextBridge (window.biiAPI) 経由で公開する。
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

// Windowsでの安定性向上のためANGLEバックエンドをデフォルトに
app.commandLine.appendSwitch('use-angle', 'default');

// GPUプロセスがクラッシュする環境があるため、ハードウェアアクセラレーションを無効化（安定性優先）
app.disableHardwareAcceleration();

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 400,
    height: 600,
    frame: false,        // フレームレス（タイトルバーなし）
    transparent: true,   // 透明背景
    alwaysOnTop: true,   // 常に最前面
    skipTaskbar: false,  // タスクバーに表示（Alt+Tab認識のため）
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile('index.html');

  // 開発者ツール（デバッグ時のみ有効化）
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
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
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// ------------------------------------------------------------------
// IPC: ウィンドウ操作
// ------------------------------------------------------------------

ipcMain.on('minimize-window', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('close-window', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.on('set-always-on-top', (event, flag) => {
  if (mainWindow) mainWindow.setAlwaysOnTop(Boolean(flag));
});

ipcMain.on('restore-window', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

ipcMain.on('hide-window', () => {
  if (mainWindow) mainWindow.hide();
});

ipcMain.on('show-window', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});

// ウィンドウ移動（レンダラーからの相対移動）
ipcMain.on('move-window', (event, { mouseX, mouseY }) => {
  if (mainWindow) {
    const { x, y } = mainWindow.getBounds();
    mainWindow.setPosition(x + mouseX, y + mouseY);
  }
});

// ------------------------------------------------------------------
// IPC: モデルファイル探索（fs はメインプロセス側でのみ使う）
// ------------------------------------------------------------------

ipcMain.handle('find-model', () => {
  const modelsDir = path.join(__dirname, 'models', 'bii');
  let modelPath = null;

  try {
    const entries = fs.readdirSync(modelsDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        const dirPath = path.join(modelsDir, entry.name);
        // 「フォルダ名.model3.json」を優先、なければフォルダ内の任意の .model3.json
        const preferred = path.join(dirPath, `${entry.name}.model3.json`);
        if (fs.existsSync(preferred)) {
          modelPath = preferred;
          break;
        }
        const inner = fs.readdirSync(dirPath).find((f) => f.endsWith('.model3.json'));
        if (inner) {
          modelPath = path.join(dirPath, inner);
          break;
        }
      } else if (entry.name.endsWith('.model3.json')) {
        modelPath = path.join(modelsDir, entry.name);
        break;
      }
    }
  } catch (e) {
    return { url: null, error: `モデルディレクトリの読み込みエラー: ${e}` };
  }

  if (!modelPath) {
    return { url: null, error: `モデルファイルが見つかりません: ${modelsDir}` };
  }

  // Windowsパス → file:// URL（スペース等はエンコード）
  let clean = modelPath.replace(/\\/g, '/');
  if (!clean.startsWith('/')) clean = '/' + clean;
  return { url: 'file://' + encodeURI(clean), error: null };
});
