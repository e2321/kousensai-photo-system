import os
import base64
from flask import Flask, request, render_template
import urllib.parse 

# --- Renderアプリケーションの初期化 ---
# template_folder='.' を削除！Renderはデフォルトで'templates'フォルダを探します
app = Flask(__name__) 

# Renderが稼働していることを確認するためのルート
@app.route('/')
def home():
    """Renderが動いていることを確認するためのシンプルなルート"""
    return "学園祭フォトブース：共有サーバーが稼働中です。", 200

@app.route('/download_page')
def download_page():
    """
    複数作品のURLリストを受け取り、復元し、ダウンロードページを表示するルート
    """
    urls_encoded = request.args.get('urls')
    
    if not urls_encoded:
        return "Error: No URLs provided.", 400
        
    try:
        urls_base64 = urllib.parse.unquote_plus(urls_encoded)
        urls_decoded = base64.b64decode(urls_base64).decode('utf-8')
        media_urls = urls_decoded.split(',')
        
        media_list = []
        image_count = 0 # 静止画のカウント用カウンター
        
        for url in media_urls:
            if url:
                file_type = 'video' if url.lower().endswith(('.mp4', '.mov')) else 'image'
                media_item = {'url': url, 'type': file_type}
                
                # 静止画の場合にのみ連番を割り当てる
                if file_type == 'image':
                    image_count += 1
                    media_item['index'] = image_count # media_listにindexを追加
                    
                media_list.append(media_item)

        # テンプレートに渡すデータは templates/download_page.html に渡される
        # ZIP機能の削除に伴い、urls_base64はテンプレート内で不要になりましたが、
        # 他の用途で必要な可能性も考慮し、残しておきますが、今回は不要です。
        return render_template('download_page.html', 
                               media_list=media_list, 
                               urls_base64=urls_base64)
                               
    except Exception as e:
        print(f"Decoding/Rendering Error: {e}") 
        return f"エラーが発生しました。再度QRコードを読み込むか、スタッフに声をかけてください。エラー情報: {e}", 500

# --- サーバー起動 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))