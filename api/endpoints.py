import os
import tempfile
import uuid
import zipfile
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional

from config import OCCT_AVAILABLE
from services.step_processor import StepUnfoldGenerator
from models.request_models import BrepPapercraftRequest

# APIルーターの作成
router = APIRouter()

# --- STEP専用APIエンドポイント ---
@router.post("/api/step/unfold")
async def unfold_step_to_svg(
    file: UploadFile = File(...),
    return_face_numbers: bool = Form(True),
    output_format: str = Form("svg"),
    layout_mode: str = Form("canvas"),
    page_format: str = Form("A4"),
    page_orientation: str = Form("portrait"),
    scale_factor: float = Form(10.0)
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図（SVG）を生成するAPI。
    
    Args:
        file: STEPファイル (.step/.stp)
        return_face_numbers: 面番号データを含むかどうか (default: True)
        output_format: 出力形式 - "svg"=SVGファイル、"json"=JSONレスポンス
        layout_mode: レイアウトモード - "canvas"=フリーキャンバス、"paged"=ページ分割 (default: "canvas")
        page_format: ページフォーマット - "A4", "A3", "Letter" (default: "A4")
        page_orientation: ページ方向 - "portrait"=縦、"landscape"=横 (default: "portrait")
        scale_factor: 図の縮尺倍率 (default: 10.0) - 例: 150なら1/150スケール
    
    Returns:
        - output_format="svg": 単一SVGファイル（pagedモードでは全ページを縦に並べて表示）
        - output_format="json": JSONレスポンス
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")
        file_content = await file.read()
        
        # StepUnfoldGeneratorインスタンスを作成
        step_unfold_generator = StepUnfoldGenerator()
        
        # STEPファイルの場合、load_from_bytesメソッドを使用し、拡張子を指定
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        if not step_unfold_generator.load_from_bytes(file_content, file_ext):
            raise HTTPException(status_code=400, detail="STEPファイルの読み込みに失敗しました。")
        output_path = os.path.join(tempfile.mkdtemp(), f"step_unfold_{uuid.uuid4()}.svg")
        
        # レイアウトオプションを含むBrepPapercraftRequestを作成
        request = BrepPapercraftRequest(
            layout_mode=layout_mode,
            page_format=page_format,
            page_orientation=page_orientation,
            scale_factor=scale_factor
        )
        svg_path, stats = step_unfold_generator.generate_brep_papercraft(request, output_path)
        
        # 出力形式に応じてレスポンスを分岐
        if output_format.lower() == "json":
            # JSONレスポンス形式
            with open(svg_path, 'r', encoding='utf-8') as svg_file:
                svg_content = svg_file.read()
            
            response_data = {
                "svg_content": svg_content,
                "stats": stats
            }
            
            try:
                os.unlink(svg_path)
            except:
                pass
            
            # 面番号データを含める場合
            if return_face_numbers:
                face_numbers = step_unfold_generator.get_face_numbers()
                response_data["face_numbers"] = face_numbers
            
            return response_data
        else:
            # SVGファイルレスポンス
            # ページモードでも単一ファイルに全ページが含まれる
            return FileResponse(
                path=svg_path,
                media_type="image/svg+xml",
                filename=f"step_unfold_{layout_mode}_{uuid.uuid4()}.svg",
                headers={
                    "X-Layout-Mode": layout_mode,
                    "X-Page-Format": page_format if layout_mode == "paged" else "N/A",
                    "X-Page-Orientation": page_orientation if layout_mode == "paged" else "N/A",
                    "X-Page-Count": str(stats.get("page_count", 1)) if layout_mode == "paged" else "1"
                }
            )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")

# --- ヘルスチェック ---
@router.get("/api/health", status_code=200)
async def api_health_check():
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "version": "1.0.0",
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["step", "stp", "brep"] if OCCT_AVAILABLE else [],
        "features": {
            "step_to_svg_unfold": OCCT_AVAILABLE,
            "face_numbering": True,
            "multi_page_layout": True,
            "canvas_layout": True,
            "paged_layout": True
        }
    }
