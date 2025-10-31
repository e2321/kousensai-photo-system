import os
from flask import Flask, request, render_template

# RenderでWebサービスとしてデプロイするため、app名を明示的に指定
app = Flask(__name__, template_folder='.')
# Renderが稼働していることを確認するためのルート
@app.route('/')
def home():
    """Renderが動いていることを確認するためのシンプルなルート"""
    # このルートがお客さんに直接表示されることは稀ですが、万が一のために。
    return "学園祭フォトブース：共有サーバーが稼働中です。", 200

@app.route('/media')
def show_media_page():
    """再生用HTMLページを表示するルート (QRコードの飛び先)"""
    
    cloudinary_url = request.args.get('url') # CloudinaryのURLをクエリパラメータ 'url' から取得

    if not cloudinary_url:
        # URLが指定されていない場合のエラーページもshow_media.htmlで表示させる
        cloudinary_url = "ERROR_URL_NOT_FOUND" 
        
    # ファイルタイプを判別
    file_type = 'image'
    if cloudinary_url.lower().endswith(('.mp4', '.mov')):
        file_type = 'video'
        
    # show_media.htmlにURLとファイルタイプを渡してページを表示
    # Renderは/mediaにアクセスされたら、このページを返すだけです。
    return render_template('show_media.html', media_url=cloudinary_url, file_type=file_type)
