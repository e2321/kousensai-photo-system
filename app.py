import os
import base64
from flask import Flask, request, render_template

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
    urls_base64 = request.args.get('urls')
    if not urls_base64:
        return "Error: No URLs provided.", 400
        
    try:
        # 1. Base64文字列をデコード
        # URLをカンマ区切りの文字列に戻す
        urls_decoded = base64.b64decode(urls_base64).decode()
        
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
        # (urls_base64は、念のためHTMLに渡しておきますが、今回は使いません)
        return render_template('download_page.html', 
                               media_list=media_list, 
                               urls_base64=urls_base64)
                               
    except Exception as e:
        # デバッグログを Renderのコンソールに出力
        print(f"Decoding Error: {e}")
        # お客さんにはエラーメッセージを返す
        return f"エラーが発生しました。再度QRコードを読み込むか、スタッフに声をかけてください。", 500

# ★★★ /zip_download ルートを削除 ★★★

# --- サーバー起動 ---
if __name__ == '__main__':
    # RenderはGunicornで実行されるため、このブロックは通常実行されない
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
