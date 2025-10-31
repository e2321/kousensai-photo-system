import os
import base64
from flask import Flask, request, render_template
import urllib.parse # ★ urllib.parse をインポート

# --- Renderアプリケーションの初期化 ---
# template_folder='.' を指定することで、Renderのルートディレクトリにある
# download_page.htmlをテンプレートとして認識させる
app = Flask(__name__, template_folder='.')

# Renderが稼働していることを確認するためのルート
@app.route('/')
def home():
    """Renderが動いていることを確認するためのシンプルなルート"""
    # RenderでこのWebサービスが稼働していることを示すシンプルなメッセージ
    return "学園祭フォトブース：共有サーバーが稼働中です。", 200

@app.route('/download_page')
def download_page():
    """
    複数作品のURLリストを受け取り、復元し、ダウンロードページを表示するルート
    このルートがお客さんがQRコードを読み込んだ後のメインページになります。
    """
    # Base64エンコードされたURLリストをクエリパラメータ 'urls' から取得
    urls_encoded = request.args.get('urls') # ★ 名前を encoded に変更
    
    if not urls_encoded:
        return "Error: No URLs provided.", 400
        
    try:
        # ★★★ 修正箇所1: URLエンコードを元に戻す ★★★
        # (例: %2B を + に戻す)
        urls_base64 = urllib.parse.unquote_plus(urls_encoded)
        
        # 1. Base64文字列をデコード
        # Base64文字列をバイト列に戻し、それを文字列にデコード
        urls_decoded = base64.b64decode(urls_base64).decode('utf-8')
        
        # 2. カンマ区切りでURLのリストに分割
        media_urls = urls_decoded.split(',')
        
        # 3. 個別プレビュー用のデータを作成
        media_list = []
        for url in media_urls:
            if url:
                # ファイルタイプを判別: 動画にはダウンロードボタンを付けない
                file_type = 'video' if url.lower().endswith(('.mp4', '.mov')) else 'image'
                media_list.append({'url': url, 'type': file_type})

        # 4. テンプレートにデータを渡してレンダリング
        return render_template('download_page.html', 
                               media_list=media_list, 
                               urls_base64=urls_base64)
                               
    except Exception as e:
        # デバッグログを Renderのコンソールに出力
        # ★ Renderのコンソールでエラーのタイプが確認できます
        print(f"Decoding/Rendering Error: {e}") 
        # お客さんにはエラーメッセージを返す
        return f"エラーが発生しました。再度QRコードを読み込むか、スタッフに声をかけてください。エラー情報: {e}", 500

# --- サーバー起動 ---
if __name__ == '__main__':
    # RenderはGunicornで実行されるため、このブロックは通常実行されない
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))