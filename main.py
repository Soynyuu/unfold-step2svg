import os
import uvicorn
from config import create_app, OCCT_AVAILABLE
from api.endpoints import router

# FastAPIアプリケーションの作成
app = create_app()

# APIルーターの追加
app.include_router(router)

def main():
    """サーバーを起動する"""
    if not OCCT_AVAILABLE:
        print("警告: OpenCASCADE が利用できないため、一部機能が制限されます。")
    
    port = int(os.getenv("PORT", 8001))
    print(f"サーバーをポート {port} で起動します。")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()