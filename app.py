import cv2
import numpy as np
import qrcode
import uuid
import base64
import io
import os
from flask import Flask, request, jsonify, send_from_directory, render_template,send_file
import moviepy.editor as mpy  # moviepy をインポート
from flask_httpauth import HTTPBasicAuth # ★ Basic認証ライブラリ

# このスクリプト(app.py)がある場所を基準にします
basedir = os.path.abspath(os.path.dirname(__file__))

# --- 設定 ---
UPLOAD_FOLDER = os.path.join(basedir, 'uploads') # ★絶対パスに変更
BACKGROUND_FOLDER = os.path.join(basedir, 'backgrounds') # ★絶対パスに変更

# ↓↓↓ ngrokを起動するたびに、ここのドメイン名を書き換える！ ↓↓↓
YOUR_NGROK_DOMAIN = "prediplomatic-kori-instrumentally.ngrok-free.dev"
# ↑↑↑ (あなたのngrokのURLに書き換えてください)

# --- アプリとBasic認証の初期化 ---
app = Flask(__name__, static_folder='.', template_folder='.')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BACKGROUND_FOLDER'] = BACKGROUND_FOLDER
auth = HTTPBasicAuth() # ★ Basic認証を初期化

# ★ 学園祭用のIDとパスワードを設定
USERS = {
    "staff": "ueno2025"
}

@auth.verify_password
def verify_password(username, password):
    """パスワードを検証する関数"""
    if username in USERS and USERS[username] == password:
        return username

# --- グリーンバックの色味設定 (HSV色空間) ---
LOWER_GREEN = np.array([35, 100, 100])
UPPER_GREEN = np.array([85, 255, 255])

# --- 合成関数 ---

def get_foreground_mask(image_data_url):
    header, encoded = image_data_url.split(",", 1)
    img_data = base64.b64decode(encoded)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
    mask_inv = cv2.bitwise_not(mask)
    fg = cv2.bitwise_and(img, img, mask=mask_inv)
    return fg, mask_inv, img.shape

def process_static_composite(fg, mask_inv, bg_image):
    bg_resized = cv2.resize(bg_image, (fg.shape[1], fg.shape[0]))
    mask = cv2.bitwise_not(mask_inv)
    bg = cv2.bitwise_and(bg_resized, bg_resized, mask=mask)
    final_image = cv2.add(fg, bg)
    image_id = str(uuid.uuid4()) + ".jpg"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], image_id)
    cv2.imwrite(save_path, final_image)
    return image_id

def process_video_composite(fg, mask_inv, bg_video_path):
    cap = cv2.VideoCapture(bg_video_path)
    if not cap.isOpened():
        print("動画ファイルが開けません:", bg_video_path)
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    fg_resized = cv2.resize(fg, (width, height))
    mask_inv_resized = cv2.resize(mask_inv, (width, height))
    mask_resized = cv2.bitwise_not(mask_inv_resized)
    processed_frames = []
    print(f"動画合成開始 (moviepy)... ( {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))} フレーム)")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        bg = cv2.bitwise_and(frame, frame, mask=mask_resized)
        final_frame_bgr = cv2.add(fg_resized, bg)
        final_frame_rgb = cv2.cvtColor(final_frame_bgr, cv2.COLOR_BGR2RGB)
        processed_frames.append(final_frame_rgb)
    cap.release()
    print("フレーム処理完了。moviepyで動画ファイル書き出し開始...")
    if not processed_frames:
        print("処理するフレームがありませんでした。")
        return None
    try:
        video_id = str(uuid.uuid4()) + ".mp4"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], video_id)
        clip = mpy.ImageSequenceClip(processed_frames, fps=fps)
        clip.write_videofile(
            save_path, 
            codec='libx264', 
            audio=False, 
            threads=4, 
            logger=None,
            ffmpeg_params=["-pix_fmt", "yuv420p"] # iPhone互換性
        )
        clip.close()
        print("動画合成完了！ (moviepy)")
        return video_id
    except Exception as e:
        print(f"moviepyでの動画書き出しエラー: {e}")
        return None

def generate_qr_code(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return "data:image/png;base64," + img_str

# --- ルート（URLの定義） ---

@app.route('/')
@auth.login_required  # ★ Basic認証
def index():
    """撮影ページ (index.html) を表示"""
    try:
        files = os.listdir(app.config['BACKGROUND_FOLDER'])
        backgrounds = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov'))]
        return render_template('index.html', backgrounds=backgrounds)
    except Exception as e:
        print(f"!!!!!! 背景フォルダの読み込みエラー: {e} !!!!!!")
        return render_template('index.html', backgrounds=[])

@app.route('/background/<filename>')
def background_file(filename):
    """背景選択用のサムネイル画像を表示"""
    return send_from_directory(app.config['BACKGROUND_FOLDER'], filename)

@app.route('/media/<filename>')
def show_media_page(filename):
    """再生用HTMLページを表示するルート (QRコードの飛び先)"""
    return render_template('show_media.html', filename=filename)

@app.route('/serve_file/<filename>')
def serve_media_file(filename):
    """show_media.html が呼び出す、ファイル供給専用ルート"""
    
    # ★ ファイルのフルパスを構築
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(file_path):
        return "File not found", 404 # ファイル存在チェック

    # MIMEタイプを決定
    mimetype = None
    if filename.lower().endswith(('.mp4', '.mov')):
        mimetype = 'video/mp4'
    elif filename.lower().endswith(('.jpg', '.jpeg')):
        mimetype = 'image/jpeg'
    elif filename.lower().endswith('.png'):
        mimetype = 'image/png'

    # ★ send_from_directory の代わりに send_file を使用
    # ★ as_attachment=False で、ダウンロードではなく「インライン表示」を明示
    response = send_file(file_path, mimetype=mimetype, as_attachment=False)
    
    # キャッシュを無効にするヘッダー
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/upload', methods=['POST'])
def upload_image():
    """撮影データと背景IDを受け取り、合成して、QRコードを返す"""
    data = request.get_json()
    image_data_url = data['image']
    background_name = data['background']

    if not background_name:
        return jsonify({"error": "背景が選択されていません"}), 400
    try:
        fg, mask_inv, shape = get_foreground_mask(image_data_url)
    except Exception as e:
        print(f"人物切り抜きエラー: {e}")
        return jsonify({"error": "画像処理に失敗"}), 500
    bg_path = os.path.join(app.config['BACKGROUND_FOLDER'], background_name)
    if not os.path.exists(bg_path):
        return jsonify({"error": "背景ファイルが見つかりません"}), 404
    file_extension = os.path.splitext(background_name)[1].lower()
    output_media_id = None
    try:
        if file_extension in ['.jpg', '.jpeg', '.png']:
            bg_image = cv2.imread(bg_path)
            output_media_id = process_static_composite(fg, mask_inv, bg_image)
        elif file_extension in ['.mp4', '.mov', '.avi']:
            output_media_id = process_video_composite(fg, mask_inv, bg_path)
        else:
            return jsonify({"error": "対応していない背景ファイル形式です"}), 400
        if output_media_id is None:
            raise Exception("合成処理に失敗しました")
    except Exception as e:
        print(f"合成エラー: {e}")
        return jsonify({"error": "合成処理に失敗"}), 500

    media_url = f"https://{YOUR_NGROK_DOMAIN}/media/{output_media_id}"
    qr_code_base_code = generate_qr_code(media_url)

    return jsonify({"qr_code": qr_code_base_code})

# --- サーバー起動 ---
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(BACKGROUND_FOLDER, exist_ok=True)
    print("==============================================")
    print(f" サーバー起動中...")
    print(f" ngrokドメインを {YOUR_NGROK_DOMAIN} に設定しました")
    print(f" PCの http://localhost:5000 で撮影画面を開いてください")
    print(" (アクセス時にID 'staff' と 'ueno2025' が必要です)")
    print("==============================================")
    app.run(host='0.0.0.0', port=5000, debug=False)