import cv2
import numpy as np
import qrcode
import uuid
import base64
import io
import os
import tempfile  # 一時ファイル作成に必要
from flask import Flask, request, jsonify, send_from_directory, render_template
import moviepy.editor as mpy
from flask_httpauth import HTTPBasicAuth
import cloudinary  # Cloudinary をインポート
import cloudinary.uploader  # アップローダーをインポート

# --- Cloudinary設定 ---
# ★★★重要★★★ この認証情報は、あなたのローカルPC上で合成とアップロードを行うために必須です。
cloudinary.config(
    cloud_name = "dnhkvoa7e",
    api_key = "645377535132842",
    api_secret = "Ocp9nSYk0Zu1NDVrMY_42tJpOXk"
)

# このスクリプト(app.py)がある場所を基準にします
basedir = os.path.abspath(os.path.dirname(__file__))

# --- 基本設定 ---
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
BACKGROUND_FOLDER = os.path.join(basedir, 'backgrounds')

# --- Renderドメイン設定 (QRコードのリンク先) ---
# ★★★重要★★★ あなたのRenderの公開URLのドメイン名に書き換えてください
YOUR_RENDER_DOMAIN = "https://kousensai-photo-system.onrender.com/" 

# --- アプリとBasic認証の初期化 ---
app = Flask(__name__, static_folder='.', template_folder='.')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BACKGROUND_FOLDER'] = BACKGROUND_FOLDER
auth = HTTPBasicAuth()

USERS = {
    "staff": "ueno2025"
}

@auth.verify_password
def verify_password(username, password):
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
    """静止画を合成し、CloudinaryにアップロードしてURLを返す"""
    bg_resized = cv2.resize(bg_image, (fg.shape[1], fg.shape[0]))
    mask = cv2.bitwise_not(mask_inv)
    bg = cv2.bitwise_and(bg_resized, bg_resized, mask=mask)
    final_image = cv2.add(fg, bg)
    
    ret, buf = cv2.imencode('.jpg', final_image)
    if not ret:
        raise Exception("静止画のエンコードに失敗")
        
    response = cloudinary.uploader.upload(
        buf.tobytes(),
        resource_type="image",
        folder="gakusai2025"
    )
    return response['secure_url']

def process_video_composite(fg, mask_inv, bg_video_path):
    """動画を合成し、CloudinaryにアップロードしてURLを返す"""
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
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        bg = cv2.bitwise_and(frame, frame, mask=mask_resized)
        final_frame_bgr = cv2.add(fg_resized, bg)
        final_frame_rgb = cv2.cvtColor(final_frame_bgr, cv2.COLOR_BGR2RGB)
        processed_frames.append(final_frame_rgb)
    cap.release()

    if not processed_frames:
        raise Exception("処理するフレームがありませんでした。")

    video_id = str(uuid.uuid4())
    save_path = os.path.join(tempfile.gettempdir(), f"{video_id}.mp4")

    try:
        clip = mpy.ImageSequenceClip(processed_frames, fps=fps)
        clip.write_videofile(
            save_path, 
            codec='libx264', 
            audio=False, 
            threads=4, 
            logger=None,
            ffmpeg_params=["-pix_fmt", "yuv420p"] 
        )
        clip.close()

        response = cloudinary.uploader.upload(
            save_path,
            resource_type="video",
            folder="gakusai2025"
        )
        
    finally:
        if os.path.exists(save_path):
            os.remove(save_path)

    return response['secure_url']

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
@auth.login_required
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

# ★★★ Renderで処理されるルートへリンクするための /upload ルート ★★★

@app.route('/upload', methods=['POST'])
def upload_image():
    """撮影データと背景IDを受け取り、合成し、QRコードを返す"""
    data = request.get_json()
    image_data_url = data['image']
    background_name = data['background']

    if not background_name:
        return jsonify({"error": "背景が選択されていません"}), 400

    output_media_url = None
    
    try:
        fg, mask_inv, shape = get_foreground_mask(image_data_url)

        bg_path = os.path.join(app.config['BACKGROUND_FOLDER'], background_name)
        if not os.path.exists(bg_path):
            return jsonify({"error": "背景ファイルが見つかりません"}), 404
        
        file_extension = os.path.splitext(background_name)[1].lower()
        
        if file_extension in ['.jpg', '.jpeg', '.png']:
            bg_image = cv2.imread(bg_path)
            output_media_url = process_static_composite(fg, mask_inv, bg_image)
        
        elif file_extension in ['.mp4', '.mov', '.avi']:
            output_media_url = process_video_composite(fg, mask_inv, bg_path)
        
        else:
            return jsonify({"error": "対応していない背景ファイル形式です"}), 400

        if output_media_url is None:
            raise Exception("合成処理またはCloudinaryへのアップロードに失敗しました")
            
    except Exception as e:
        print(f"合成エラー: {e}")
        return jsonify({"error": "合成処理に失敗"}), 500

    # --- 5. QRコードを生成（RenderのURLに誘導） ---
    # RenderのWebサービスに誘導し、CloudinaryのURLを渡す
    qr_target_url = f"https://{YOUR_RENDER_DOMAIN}/media?url={output_media_url}"
    qr_code_base_code = generate_qr_code(qr_target_url)

    return jsonify({"qr_code": qr_code_base_code})

# --- サーバー起動 ---
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(BACKGROUND_FOLDER, exist_ok=True)
    
    print("==============================================")
    print(" ★★★ ローカル合成サーバー起動 (Renderへはプッシュしない) ★★★")
    print(f" QRリンク先ドメイン: {YOUR_RENDER_DOMAIN}")
    print(" PCの http://localhost:5000 で撮影画面を開いてください")
    print("==============================================")
    
    app.run(host='0.0.0.0', port=5000, debug=False)