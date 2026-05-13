/**
 * Live2Dモデルを表示・制御するレンダラープロセス
 */

const { ipcRenderer } = require('electron');
const WebSocket = require('ws');

// グローバル変数
let app = null;
let model = null;
let ws = null;
let isConnected = false;
let subtitleTimer = null; // 字幕消去用タイマー

// ステータス表示
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const loading = document.getElementById('loading');
const canvas = document.getElementById('live2d-canvas');
const chatInput = document.getElementById('chat-input');
const subtitleContainer = document.getElementById('subtitle-container');
const logContainer = document.getElementById('log-container');
const logContent = document.getElementById('log-content');

// コントロールボタン
document.getElementById('minimize-btn').addEventListener('click', () => {
    ipcRenderer.send('minimize-window');
});

document.getElementById('close-btn').addEventListener('click', () => {
    ipcRenderer.send('close-window');
});

// ログボタン
document.getElementById('log-btn').addEventListener('click', () => {
    if (logContainer.style.display === 'none') {
        logContainer.style.display = 'flex';
    } else {
        logContainer.style.display = 'none';
    }
});


document.getElementById('log-close-btn').addEventListener('click', () => {
    logContainer.style.display = 'none';
});

// 視覚ボタン（画面を見せる）
const visionBtn = document.getElementById('vision-btn');
if (visionBtn) {
    visionBtn.addEventListener('click', () => {
        if (!ws || !isConnected) {
            console.warn('Cannot send: WebSocket not connected');
            return;
        }

        // ユーザーの要望により、最小化・非表示を廃止し、即座に全画面撮影を行う
        // （キャラクターが映り込むが、速度優先）

        // WebSocketの状態を確認
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not OPEN or null.');
            return;
        }

        try {
            // 入力欄のテキストを取得
            const userText = chatInput.value.trim();

            // ペイロードを作成
            const payload = {
                type: 'vision_request',
                text: userText // テキストがあれば含める、なければ空文字
            };

            ws.send(JSON.stringify(payload));
            console.log('Vision request sent successfully via WebSocket:', payload);

            addLog('user', userText ? `(画面を見せています: "${userText}")` : '(画面を見せています...)');
            showSubtitle('（画面を見ています...）');

            // 送信したら入力欄をクリアしてもいいが、
            // ユーザーが「続けて何か打ちたい」かもしれないので、
            // ここでは送信済みということクリアする（Enter送信と同じ挙動）
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
            if (text) {
                if (ws && isConnected) {
                    ws.send(JSON.stringify({
                        type: 'user_input',
                        text: text
                    }));
                    addLog('user', text); // ログに追加
                    showSubtitle(text);   // 字幕表示（自分の発言も見せる）
                    chatInput.value = ''; // 送信後にクリア
                    console.log('User input sent:', text);
                } else {
                    console.warn('Cannot send: WebSocket not connected');
                }
            }
        }
    });
}

// WebSocket接続（Pythonバックエンドと通信）
function connectToBackend() {
    ws = new WebSocket('ws://localhost:8765');

    ws.on('open', () => {
        isConnected = true;
        updateStatus('connected', '✓ Pythonサーバー接続完了');
        console.log('Pythonサーバーに接続しました');
    });

    ws.on('message', (data) => {
        try {
            const message = JSON.parse(data);
            handleMessage(message);
        } catch (e) {
            console.error('メッセージ解析エラー:', e);
        }
    });

    ws.on('error', (error) => {
        console.error('WebSocketエラー:', error);
        updateStatus('disconnected', '✗ 接続エラー');
    });

    ws.on('close', () => {
        isConnected = false;
        updateStatus('disconnected', '✗ 切断');
        // 再接続を試行
        setTimeout(connectToBackend, 3000);
    });
}

function updateStatus(status, text) {
    statusIndicator.className = `status-indicator ${status}`;
    statusIndicator.textContent = text;
    if (statusText) {
        statusText.textContent = text;
    }
}

// ログ追加関数
function addLog(type, text) {
    if (!logContent) return;

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    // 時間表示
    const time = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = time;

    entry.appendChild(timestamp);
    entry.appendChild(document.createTextNode(text));

    logContent.appendChild(entry);
    // 最下部にスクロール
    logContent.scrollTop = logContent.scrollHeight;
}

// 字幕表示関数
function showSubtitle(text) {
    if (!subtitleContainer) return;

    subtitleContainer.textContent = text;
    subtitleContainer.style.opacity = '1';

    // 既存タイマーをクリア
    if (subtitleTimer) {
        clearTimeout(subtitleTimer);
    }

    // 5秒後に消す
    subtitleTimer = setTimeout(() => {
        subtitleContainer.style.opacity = '0';
    }, 5000);
}

function handleMessage(message) {
    switch (message.type) {
        case 'emotion':
        case 'expression':
            // 表情を変更
            if (model) {
                // message.emotion または message.name を使用
                const emotionName = message.emotion || message.name;
                if (emotionName) {
                    setExpression(emotionName);
                }
            }
            break;
        case 'motion':
            // モーションを再生
            if (model && message.motion) {
                playMotion(message.motion);
            }
            break;
        case 'lipsync':
            // リップシンク（口の開閉）
            if (model) {
                // Live2Dのパラメータを直接操作
                // Cubism 3/4/5 standard parameter
                try {
                    // 0.0 ~ 1.0の値を設定
                    const value = Math.min(1.0, Math.max(0.0, parseFloat(message.value)));

                    // 目標値を設定（直接適用せず、アニメーションループで補間する）
                    model.targetMouthValue = value;
                } catch (e) {
                    // エラー無視（頻繁に呼ばれるため）
                }
            }
            break;

        case 'response':
            // AIからの応答テキスト
            if (message.text) {
                // バックアップとしてここでも復帰を入れる
                ipcRenderer.send('restore-window');

                showSubtitle(message.text);
                addLog('bot', message.text);
            }
            break;

        case 'restore':
            // サーバーからの明示的な復帰信号（撮影完了直後など）
            console.log('Received restore signal');
            ipcRenderer.send('restore-window');
            break;

        case 'status':
            // ステータス更新
            if (message.status) {
                console.log('Status:', message.status);
                // サーバーからのステータスを表示しない（ログには出さない）
            }
            break;
    }
}


// Live2Dモデルの初期化
async function initLive2D() {
    try {
        // キャンバスのサイズを確認
        console.log('Canvas size:', canvas.width, canvas.height, canvas.clientWidth, canvas.clientHeight);

        // WebGLが利用可能か確認（複数の方法で試行）
        let gl = null;
        const testCanvas = document.createElement('canvas');

        // 通常のWebGLコンテキストを試行
        try {
            gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl');
        } catch (e) {
            console.warn('WebGLコンテキスト取得エラー:', e);
        }

        // WebGL2を試行
        if (!gl) {
            try {
                gl = testCanvas.getContext('webgl2');
            } catch (e) {
                console.warn('WebGL2コンテキスト取得エラー:', e);
            }
        }

        console.log('WebGL context available:', gl !== null);

        if (!gl) {
            console.warn('⚠️ WebGL check failed, but proceeding (will attempt software rendering)');
        }

        // PixiJSアプリケーションを作成
        // ハードウェアアクセラレーションが無効な場合、自動的にソフトウェアレンダリング（Canvas/SwiftShader）が使用されます
        app = new PIXI.Application({
            view: canvas,
            autoStart: true,
            width: canvas.clientWidth || 400,
            height: canvas.clientHeight || 600,
            transparent: true,  // 背景透過
            antialias: false,   // CPU負荷軽減のためアンチエイリアスを無効化
            // backgroundColor: 0x2c3e50, // 背景色を無効化
            forceCanvas: false,  // WebGLを優先するが、なければCanvasを使用
            powerPreference: 'low-power'
        });

        // フレームレートを24FPS（アニメ調）に制限してCPU負荷を大幅軽減
        app.ticker.maxFPS = 24;

        console.log('PIXI App created:', app.screen.width, app.screen.height);
        console.log('Renderer type:', app.renderer.type);
        console.log('Renderer type name:', app.renderer.type === PIXI.RENDERER_TYPE.WEBGL ? 'WebGL' : app.renderer.type === PIXI.RENDERER_TYPE.CANVAS ? 'Canvas2D' : 'Unknown');
        console.log('WebGL supported:', app.renderer.gl !== null);

        // WebGLが利用できない場合の警告
        if (app.renderer.type === PIXI.RENDERER_TYPE.CANVAS) {
            console.error('❌ Canvas2Dレンダラーが使用されています。Live2DモデルはWebGLが必要です。');
            console.error('通常のpixi.jsを使用してください（pixi.js-legacyではなく）');
        } else if (app.renderer.type === PIXI.RENDERER_TYPE.WEBGL) {
            console.log('✓ WebGLレンダラーが使用されています');
        }



        // Live2Dモデルを読み込む
        // Electronでは、__dirnameを使用して絶対パスを取得します
        const path = require('path');
        const fs = require('fs');

        // モデルファイルのパスを検索
        const modelsDir = path.join(__dirname, 'models', 'bii');
        let modelPath = null;

        // モデルファイルを検索
        try {
            const files = fs.readdirSync(modelsDir, { withFileTypes: true });
            for (const file of files) {
                if (file.isDirectory()) {
                    const modelFile = path.join(modelsDir, file.name, `${file.name}.model3.json`);
                    if (fs.existsSync(modelFile)) {
                        modelPath = modelFile;
                        console.log(`モデルファイルを発見: ${modelPath}`);
                        break;
                    }
                } else if (file.name.endsWith('.model3.json')) {
                    modelPath = path.join(modelsDir, file.name);
                    console.log(`モデルファイルを発見: ${modelPath}`);
                    break;
                }
            }
        } catch (dirError) {
            console.error('モデルディレクトリの読み込みエラー:', dirError);
        }

        // デフォルトパスを試す
        const defaultPaths = [
            path.join(modelsDir, 'Usa Maid', 'Usa Maid.model3.json'),
            path.join(modelsDir, 'model.model3.json'),
            path.join(modelsDir, 'bii.model3.json')
        ];

        if (!modelPath) {
            for (const defaultPath of defaultPaths) {
                if (fs.existsSync(defaultPath)) {
                    modelPath = defaultPath;
                    console.log(`デフォルトパスでモデルファイルを発見: ${modelPath}`);
                    break;
                }
            }
        }

        if (!modelPath) {
            throw new Error(`モデルファイルが見つかりません。以下のいずれかのパスに配置してください:\n${defaultPaths.join('\n')}`);
        }

        try {
            console.log(`Live2Dモデルを読み込み中: ${modelPath}`);
            console.log('PIXI.live2d:', PIXI.live2d);
            console.log('PIXI.live2d.Live2DModel:', PIXI.live2d?.Live2DModel);

            // PIXI.live2dが正しく初期化されているか確認
            if (!PIXI.live2d || !PIXI.live2d.Live2DModel) {
                throw new Error('PIXI.live2d.Live2DModelが利用できません。pixi-live2d-displayが正しく初期化されていない可能性があります。');
            }

            // パスを正規化（Windows対応、スペースのエスケープ）
            let cleanPath = modelPath.replace(/\\/g, '/');
            // ドライブレターの前にスラッシュを追加（例: C:/... -> /C:/...）
            if (!cleanPath.startsWith('/')) {
                cleanPath = '/' + cleanPath;
            }
            // URLエンコード（スペースなどを%20に）
            const modelUrl = 'file://' + encodeURI(cleanPath);

            console.log(`Original Path: ${modelPath}`);
            console.log(`Clean Path: ${cleanPath}`);
            console.log(`Loading URL: ${modelUrl}`);

            model = await PIXI.live2d.Live2DModel.from(modelUrl);

            console.log('Model loaded:', model.width, model.height);
            console.log('Model scale:', model.scale.x, model.scale.y);
            console.log('Model internalModel:', model.internalModel);
            console.log('Model textures:', model.textures);
            console.log('Model children:', model.children.length);

            // モデルのアンカーポイントを中央に設定
            model.anchor.set(0.5, 0.5);

            // モデルの可視性を明示的に設定
            model.visible = true;
            model.alpha = 1.0;

            // アイドルモーションを無効化（勝手に動かないようにする）
            if (model.internalModel) {
                // これで勝手に視線などが動かなくなる
                model.internalModel.motionManager.stopAllMotions();
            }

            // ドラッグによる視線追従を無効化
            model.interactive = true; // ただしマウスイベントは受け取る（移動拡縮のため）
            model.autoInteract = false; // 自動視線追従をOFF



            // モデルをステージに追加
            app.stage.addChild(model);
            console.log('Model added to stage, total children:', app.stage.children.length);

            // モデルを中央（横）の下端付近（縦）に配置
            // 頭が見切れないよう、さらに下げる (0.65 -> 0.9)
            model.x = app.screen.width / 2;
            model.y = app.screen.height * 0.9;

            // モデルのサイズを調整（画面に収まるように、最小スケールを設定）
            const scaleX = (app.screen.width * 0.9) / model.width;
            const scaleY = (app.screen.height * 0.9) / model.height;
            let scale = Math.min(scaleX, scaleY);

            // 最小スケールを0.3に設定（小さすぎないように）
            scale = Math.max(scale, 0.3);
            // 最大スケールを1.5に設定（大きすぎないように）
            scale = Math.min(scale, 1.5);

            model.scale.set(scale);

            console.log('Model positioned:', model.x, model.y, 'scale:', scale);
            console.log('Model visible:', model.visible, 'alpha:', model.alpha);
            console.log('Model bounds:', model.getBounds());
            console.log('Model worldTransform:', model.worldTransform);

            // モデルが正しく表示されているか確認
            model.on('added', () => {
                console.log('Model added to stage');
            });

            // モデルの初期化を待つ
            await new Promise(resolve => setTimeout(resolve, 200));

            // レンダリングを強制（複数回試行）
            for (let i = 0; i < 5; i++) {
                app.renderer.render(app.stage);
                await new Promise(resolve => setTimeout(resolve, 50));
            }

            console.log('Rendering forced, model should be visible');
            console.log('Model internal state:', {
                initialized: model.internalModel ? true : false,
                texturesLoaded: model.textures.length,
                childrenCount: model.children.length
            });

            // ローディング表示を非表示
            if (loading) {
                loading.style.display = 'none';
            }

            updateStatus('connected', '✓ Live2D読み込み完了');
            console.log('Live2Dモデルを読み込みました:', modelPath);
        } catch (modelError) {
            console.error('Live2Dモデルの読み込みに失敗:', modelError);
            console.error('エラー詳細:', modelError.message);
            console.error('スタックトレース:', modelError.stack);
            // モデルファイルがない場合は、プレースホルダーを表示
            if (loading) {
                loading.innerHTML = `
                    <h2>🐱 猫使ビィ</h2>
                    <p style="color: #ff6b6b;">Live2Dモデルの読み込みに失敗しました</p>
                    <p style="font-size: 10px; margin-top: 10px;">
                        エラー: ${modelError.message}<br>
                        モデルファイルのパス: ${modelPath || '見つかりません'}<br>
                        コンソールで詳細を確認してください（F12）
                    </p>
                `;
            }
            throw modelError;
        }

        // アニメーションループ
        app.ticker.add(() => {
            if (model) {
                // リップシンクロスムージング（線形補間）
                if (typeof model.targetMouthValue === 'number') {
                    if (typeof model.currentMouthValue !== 'number') model.currentMouthValue = 0;

                    // 現在値から目標値へ 30% ずつ近づける（スムーズ化）
                    model.currentMouthValue += (model.targetMouthValue - model.currentMouthValue) * 0.3;

                    if (model.internalModel && model.internalModel.coreModel) {
                        model.internalModel.coreModel.setParameterValueById('ParamMouthOpenY', model.currentMouthValue);
                    }
                }

                // Live2Dモデルの更新
                model.update(app.ticker.deltaTime);

                // デバッグ：定期的にモデルの状態を確認
                if (app.ticker.lastTime % 1000 < 16) {  // 約1秒ごと
                    // ログ過多を防ぐためコメントアウト
                    /*
                    console.log('Model internal state:', {
                       initialized: model.internalModel ? true : false,
                       texturesLoaded: model.textures.length,
                       childrenCount: model.children.length,
                       expressions: model.internalModel.settings.expressions
                    });
                    */
                }
            }
        });

        // レンダリングループを強制的に開始
        app.start();

    } catch (error) {
        console.error('Live2D初期化エラー:', error);
        updateStatus('disconnected', '✗ 初期化エラー');
    }
}

// 表情を設定
function setExpression(emotion) {
    if (!model) return;

    // 感情タグから表情名にマッピング
    // 注意: 実際のモデルの表情ファイル名に合わせて調整してください
    const expressionMap = {
        'Happy': 'happy',      // happy.exp3.json
        'Sad': 'sad',          // sad.exp3.json
        'Angry': 'angry',      // angry.exp3.json
        'Surprised': 'surprised', // surprised.exp3.json (renamed from shock)
        'Shock': 'surprised',  // shockもsurprisedに対応
        'Neutral': null        // neutralファイルがない場合は指定しない
    };

    const expressionName = expressionMap[emotion] || 'neutral';

    // Live2Dの表情ファイルを読み込んで適用
    try {
        // 利用可能な表情を確認（デバッグ用）
        if (model.internalModel && model.internalModel.settings) {
            const availableExpressions = model.internalModel.settings.expressions;
            console.log('Available expressions:', availableExpressions);
            // expressionsが配列の場合、Nameプロパティなどがキーになることが多い
        }

        // PixiJS Live2D Displayのexpression()メソッドを使用
        if (model.expression) {
            // インデックスまたは名前で指定
            // 定義されている名前と一致する必要がある
            model.expression(expressionName);
            console.log(`表情適用試行: ${expressionName} (from ${emotion})`);
        } else {
            // expression()メソッドが利用できない場合のフォールバック
            console.warn('expression()メソッドが利用できません。表情ファイルが正しく配置されているか確認してください。');
        }
    } catch (e) {
        console.warn(`表情設定エラー (${expressionName}):`, e);
    }
}

// モーションを再生
function playMotion(motionName) {
    if (!model) return;

    // モーションを再生
    // 注意: 実際のモデルのモーション名に合わせて調整してください
    try {
        model.motion(motionName, 0, PIXI.live2d.MotionPriority.NORMAL);
    } catch (e) {
        console.warn('モーション再生エラー:', e);
    }
}

// 初期化
window.addEventListener('DOMContentLoaded', () => {
    // PIXI.live2dが利用可能になるまで待つ
    function waitForPixiLive2D() {
        if (window.PIXI && window.PIXI.live2d && window.PIXI.live2d.Live2DModel) {
            console.log('PIXI.live2dが利用可能になりました');
            initLive2D();
            connectToBackend();
        } else {
            console.log('PIXI.live2dを待機中...', {
                PIXI: !!window.PIXI,
                live2d: !!window.PIXI?.live2d,
                Live2DModel: !!window.PIXI?.live2d?.Live2DModel
            });
            setTimeout(waitForPixiLive2D, 100);
        }
    }

    waitForPixiLive2D();
});

// ウィンドウリサイズ時の処理
// ウィンドウリサイズ時の処理
window.addEventListener('resize', () => {
    if (app && model) {
        // キャンバスのサイズを更新
        app.renderer.resize(canvas.clientWidth || 400, canvas.clientHeight || 600);

        // 注: リサイズ時に位置やスケールをリセットしないようにしました
        // ユーザーが調整した位置を維持します
    }
});

// マウス操作によるドラッグ移動
// 左クリック: モデル移動
// 右クリック: ウィンドウ移動
let isDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let modelStartX = 0;
let modelStartY = 0;
let dragButton = -1; // 0: Left, 2: Right

// 右クリックメニューを無効化（ドラッグ用）
window.addEventListener('contextmenu', (e) => {
    e.preventDefault();
});

canvas.addEventListener('mousedown', (e) => {
    if (!model) return;

    isDragging = true;
    dragButton = e.button;
    dragStartX = e.screenX; // ウィンドウ移動にはscreenXを使用
    dragStartY = e.screenY;

    if (dragButton === 0) {
        // モデル移動用初期値 (こちらはclient座標で計算)
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        modelStartX = model.x;
        modelStartY = model.y;
        canvas.style.cursor = 'grabbing';
    } else if (dragButton === 2) {
        // ウィンドウ移動用
        canvas.style.cursor = 'move';
    }

    console.log('Mouse down:', e.button);
});

window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;

    if (dragButton === 0 && model) {
        // モデル移動
        const dx = e.clientX - dragStartX;
        const dy = e.clientY - dragStartY;
        model.x = modelStartX + dx;
        model.y = modelStartY + dy;
    } else if (dragButton === 2) {
        // ウィンドウ移動 (IPC送信)
        const dx = e.screenX - dragStartX;
        const dy = e.screenY - dragStartY;

        // 移動したら基準点を更新
        dragStartX = e.screenX;
        dragStartY = e.screenY;

        if (dx !== 0 || dy !== 0) {
            ipcRenderer.send('move-window', { mouseX: dx, mouseY: dy });
        }
    }
});

window.addEventListener('mouseup', () => {
    isDragging = false;
    dragButton = -1;
    canvas.style.cursor = 'default';
});

// キーボード操作は無効化（誤操作防止のため）
/*
window.addEventListener('keydown', (e) => {
    // ...
});
*/

// マウスホイールで拡大縮小
window.addEventListener('wheel', (e) => {
    if (!model) return;

    const scaleStep = 0.05;
    // 下に回すと縮小、上に回すと拡大
    const delta = e.deltaY > 0 ? -scaleStep : scaleStep;

    const newScale = Math.max(0.05, model.scale.x + delta);
    model.scale.set(newScale);
});
