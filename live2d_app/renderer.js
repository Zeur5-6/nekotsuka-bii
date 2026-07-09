/**
 * Live2Dモデルを表示・制御するレンダラープロセス
 *
 * - PIXI / PIXI.live2d は index.html の <script> タグ（UMDビルド）で読み込み済み
 * - ウィンドウ操作・モデル探索は preload.js の window.biiAPI 経由
 * - Pythonサーバーとの通信はブラウザ標準の WebSocket を使用
 */

// グローバル変数
let app = null;
let model = null;
let ws = null;
let isConnected = false;
let subtitleTimer = null;

const WS_URL = 'ws://localhost:8765';

// DOM要素
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const loading = document.getElementById('loading');
const canvas = document.getElementById('live2d-canvas');
const chatInput = document.getElementById('chat-input');
const subtitleContainer = document.getElementById('subtitle-container');
const logContainer = document.getElementById('log-container');
const logContent = document.getElementById('log-content');

// ------------------------------------------------------------------
// コントロールボタン
// ------------------------------------------------------------------

document.getElementById('minimize-btn').addEventListener('click', () => {
    window.biiAPI.minimizeWindow();
});

document.getElementById('close-btn').addEventListener('click', () => {
    window.biiAPI.closeWindow();
});

document.getElementById('log-btn').addEventListener('click', () => {
    logContainer.style.display =
        logContainer.style.display === 'none' ? 'flex' : 'none';
});

document.getElementById('log-close-btn').addEventListener('click', () => {
    logContainer.style.display = 'none';
});

// 視覚ボタン（画面を見せる）
const visionBtn = document.getElementById('vision-btn');
if (visionBtn) {
    visionBtn.addEventListener('click', () => {
        if (!ws || !isConnected || ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot send: WebSocket not connected');
            return;
        }
        try {
            const userText = chatInput.value.trim();
            ws.send(JSON.stringify({ type: 'vision_request', text: userText }));
            addLog('user', userText ? `(画面を見せています: "${userText}")` : '(画面を見せています...)');
            showSubtitle('（画面を見ています...）');
            chatInput.value = '';
        } catch (e) {
            console.error('Failed to send vision request:', e);
        }
    });
}

// チャット入力ハンドリング
if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
        // IME入力中（変換中）でないEnterのみ反応
        if (e.key === 'Enter' && !e.isComposing) {
            const text = chatInput.value.trim();
            if (!text) return;
            if (ws && isConnected && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'user_input', text }));
                addLog('user', text);
                showSubtitle(text);
                chatInput.value = '';
            } else {
                console.warn('Cannot send: WebSocket not connected');
            }
        }
    });
}

// ------------------------------------------------------------------
// WebSocket接続（Pythonバックエンドと通信）
// ------------------------------------------------------------------

function connectToBackend() {
    ws = new WebSocket(WS_URL);

    ws.addEventListener('open', () => {
        isConnected = true;
        updateStatus('connected', '✓ Pythonサーバー接続完了');
        console.log('Pythonサーバーに接続しました');
    });

    ws.addEventListener('message', (event) => {
        try {
            handleMessage(JSON.parse(event.data));
        } catch (e) {
            console.error('メッセージ解析エラー:', e);
        }
    });

    ws.addEventListener('error', (error) => {
        console.error('WebSocketエラー:', error);
        updateStatus('disconnected', '✗ 接続エラー');
    });

    ws.addEventListener('close', () => {
        isConnected = false;
        updateStatus('disconnected', '✗ 切断');
        setTimeout(connectToBackend, 3000); // 再接続
    });
}

function updateStatus(status, text) {
    statusIndicator.className = `status-indicator ${status}`;
    statusIndicator.textContent = text;
    if (statusText) {
        statusText.textContent = text;
    }
}

function addLog(type, text) {
    if (!logContent) return;

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    const time = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = time;

    entry.appendChild(timestamp);
    entry.appendChild(document.createTextNode(text));

    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

function showSubtitle(text) {
    if (!subtitleContainer) return;

    subtitleContainer.textContent = text;
    subtitleContainer.style.opacity = '1';

    if (subtitleTimer) {
        clearTimeout(subtitleTimer);
    }
    subtitleTimer = setTimeout(() => {
        subtitleContainer.style.opacity = '0';
    }, 5000);
}

function handleMessage(message) {
    switch (message.type) {
        case 'emotion':
        case 'expression':
            if (model) {
                const emotionName = message.emotion || message.name;
                if (emotionName) {
                    setExpression(emotionName);
                }
            }
            break;

        case 'motion':
            if (model && message.motion) {
                playMotion(message.motion);
            }
            break;

        case 'lipsync':
            // 口の開き（0.0〜1.0）。ティッカー側で補間して適用する
            if (model) {
                const value = Math.min(1.0, Math.max(0.0, parseFloat(message.value)));
                if (!Number.isNaN(value)) {
                    model.targetMouthValue = value;
                }
            }
            break;

        case 'mouth_form':
            // 口の形（-1.0〜1.0）。「い」「う」などの口形状を表現する
            if (model) {
                const value = Math.min(1.0, Math.max(-1.0, parseFloat(message.value)));
                if (!Number.isNaN(value)) {
                    model.targetMouthForm = value;
                }
            }
            break;

        case 'response':
            if (message.text) {
                window.biiAPI.restoreWindow(); // 最小化からの復帰（保険）
                showSubtitle(message.text);
                addLog('bot', message.text);
            }
            break;

        case 'restore':
            // サーバーからの明示的な復帰信号（撮影完了直後など）
            window.biiAPI.restoreWindow();
            break;

        case 'status':
            if (message.status) {
                console.log('Status:', message.status);
            }
            break;
    }
}

// ------------------------------------------------------------------
// Live2Dモデルの初期化
// ------------------------------------------------------------------

async function initLive2D() {
    try {
        app = new PIXI.Application({
            view: canvas,
            autoStart: true,
            width: canvas.clientWidth || 400,
            height: canvas.clientHeight || 600,
            transparent: true,
            antialias: false,        // CPU負荷軽減
            powerPreference: 'low-power',
        });

        // フレームレートを24FPSに制限してCPU負荷を軽減
        app.ticker.maxFPS = 24;

        console.log('PIXI App created:', app.screen.width, app.screen.height,
            'renderer:', app.renderer.type === PIXI.RENDERER_TYPE.WEBGL ? 'WebGL' : 'Canvas2D');

        // モデルファイルをメインプロセス経由で探索
        const { url: modelUrl, error } = await window.biiAPI.findModel();
        if (!modelUrl) {
            throw new Error(error || 'モデルファイルが見つかりません');
        }
        console.log(`Live2Dモデルを読み込み中: ${modelUrl}`);

        model = await PIXI.live2d.Live2DModel.from(modelUrl);

        model.anchor.set(0.5, 0.5);
        model.visible = true;
        model.alpha = 1.0;

        // アイドルモーションを無効化（勝手に動かないようにする）
        if (model.internalModel) {
            model.internalModel.motionManager.stopAllMotions();
        }

        // ドラッグによる自動視線追従をOFF（マウスイベント自体は移動・拡縮で使う）
        model.interactive = true;
        model.autoInteract = false;

        app.stage.addChild(model);

        // モデルを中央（横）・下端付近（縦）に配置
        model.x = app.screen.width / 2;
        model.y = app.screen.height * 0.9;

        // 画面に収まるようスケール調整
        const scaleX = (app.screen.width * 0.9) / model.width;
        const scaleY = (app.screen.height * 0.9) / model.height;
        let scale = Math.min(scaleX, scaleY);
        scale = Math.max(scale, 0.3);
        scale = Math.min(scale, 1.5);
        model.scale.set(scale);

        console.log('Model loaded:', model.width, model.height, 'scale:', scale);

        if (loading) {
            loading.style.display = 'none';
        }
        updateStatus('connected', '✓ Live2D読み込み完了');

        // アニメーションループ: リップシンクのスムージング
        app.ticker.add(() => {
            if (!model) return;

            const core = model.internalModel && model.internalModel.coreModel;

            // 口の開き（ParamMouthOpenY）: 目標値へ30%ずつ補間
            if (typeof model.targetMouthValue === 'number') {
                if (typeof model.currentMouthValue !== 'number') model.currentMouthValue = 0;
                model.currentMouthValue +=
                    (model.targetMouthValue - model.currentMouthValue) * 0.3;
                if (core) {
                    core.setParameterValueById('ParamMouthOpenY', model.currentMouthValue);
                }
            }

            // 口の形（ParamMouthForm）: 「い」「う」などの形状
            if (typeof model.targetMouthForm === 'number') {
                if (typeof model.currentMouthForm !== 'number') model.currentMouthForm = 0;
                model.currentMouthForm +=
                    (model.targetMouthForm - model.currentMouthForm) * 0.3;
                if (core) {
                    core.setParameterValueById('ParamMouthForm', model.currentMouthForm);
                }
            }

            model.update(app.ticker.deltaTime);
        });

        app.start();

    } catch (error) {
        console.error('Live2D初期化エラー:', error);
        updateStatus('disconnected', '✗ 初期化エラー');
        if (loading) {
            loading.innerHTML = `
                <h2>🐱 Bii</h2>
                <p style="color: #ff6b6b;">Live2Dモデルの読み込みに失敗しました</p>
                <p style="font-size: 10px; margin-top: 10px;">
                    エラー: ${error.message}<br>
                    live2d_app/models/bii/ にモデルを配置してください
                </p>
            `;
        }
    }
}

// ------------------------------------------------------------------
// 表情・モーション
// ------------------------------------------------------------------

function setExpression(emotion) {
    if (!model) return;

    // Python側から届くタグ名（Happy等）→ 表情名（happy等）
    // モデルの表情名は基本的にファイル名の小文字。別名だけ吸収する
    const aliases = { Shock: 'surprised' };

    if (emotion === 'Neutral') {
        // Neutral は表情リセット
        try {
            const em = model.internalModel &&
                model.internalModel.motionManager &&
                model.internalModel.motionManager.expressionManager;
            if (em && typeof em.resetExpression === 'function') {
                em.resetExpression();
            }
        } catch (e) {
            console.warn('表情リセットエラー:', e);
        }
        return;
    }

    const expressionName = aliases[emotion] || emotion.toLowerCase();
    try {
        if (model.expression) {
            model.expression(expressionName);
            console.log(`表情適用: ${expressionName} (from ${emotion})`);
        }
    } catch (e) {
        console.warn(`表情設定エラー (${expressionName}):`, e);
    }
}

function playMotion(motionName) {
    if (!model) return;
    try {
        model.motion(motionName, 0, PIXI.live2d.MotionPriority.NORMAL);
    } catch (e) {
        console.warn('モーション再生エラー:', e);
    }
}

// ------------------------------------------------------------------
// マウス操作
// 左ドラッグ: モデル移動 / 右ドラッグ: ウィンドウ移動 / Ctrl+ホイール: 拡大縮小
// ------------------------------------------------------------------

let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let modelStartX = 0;
let modelStartY = 0;
let dragButton = -1;

window.addEventListener('contextmenu', (e) => {
    e.preventDefault(); // 右クリックメニューを無効化（ドラッグ用）
});

canvas.addEventListener('mousedown', (e) => {
    if (!model) return;

    isDragging = true;
    dragButton = e.button;

    if (dragButton === 0) {
        // モデル移動（client座標で計算）
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        modelStartX = model.x;
        modelStartY = model.y;
        canvas.style.cursor = 'grabbing';
    } else if (dragButton === 2) {
        // ウィンドウ移動（screen座標で計算）
        dragStartX = e.screenX;
        dragStartY = e.screenY;
        canvas.style.cursor = 'move';
    }
});

window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;

    if (dragButton === 0 && model) {
        model.x = modelStartX + (e.clientX - dragStartX);
        model.y = modelStartY + (e.clientY - dragStartY);
    } else if (dragButton === 2) {
        const dx = e.screenX - dragStartX;
        const dy = e.screenY - dragStartY;
        dragStartX = e.screenX;
        dragStartY = e.screenY;
        if (dx !== 0 || dy !== 0) {
            window.biiAPI.moveWindow(dx, dy);
        }
    }
});

window.addEventListener('mouseup', () => {
    isDragging = false;
    dragButton = -1;
    canvas.style.cursor = 'default';
});

// Ctrl+ホイールで拡大縮小（誤操作防止のため修飾キー必須）
window.addEventListener('wheel', (e) => {
    if (!model || !e.ctrlKey) return;
    e.preventDefault();

    const scaleStep = 0.05;
    const delta = e.deltaY > 0 ? -scaleStep : scaleStep;
    const newScale = Math.max(0.05, model.scale.x + delta);
    model.scale.set(newScale);
}, { passive: false });

// ------------------------------------------------------------------
// リサイズ・起動
// ------------------------------------------------------------------

window.addEventListener('resize', () => {
    if (app) {
        app.renderer.resize(canvas.clientWidth || 400, canvas.clientHeight || 600);
        // ユーザーが調整したモデル位置・スケールは維持する
    }
});

window.addEventListener('DOMContentLoaded', () => {
    if (!window.PIXI || !window.PIXI.live2d || !window.PIXI.live2d.Live2DModel) {
        console.error('PIXI / pixi-live2d-display が読み込まれていません。' +
            'live2d_app で npm install を実行してください。');
        updateStatus('disconnected', '✗ ライブラリ読み込みエラー');
        return;
    }
    initLive2D();
    connectToBackend();
});
