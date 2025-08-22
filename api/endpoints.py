import os
import tempfile
import uuid
import zipfile
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional

from config import OCCT_AVAILABLE
from services.step_processor import StepUnfoldGenerator
from services.citygml_processor import CityGMLProcessor, CityGMLProcessingOptions
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

# --- CityGML専用APIエンドポイント ---
@router.post("/api/citygml/to-step")
async def convert_citygml_to_step(
    file: UploadFile = File(...),
    preferred_lod: Optional[int] = Form(2),
    min_building_area: Optional[float] = Form(None),
    max_building_count: Optional[int] = Form(None),
    tolerance: Optional[float] = Form(1e-6),
    export_individual_files: Optional[bool] = Form(False),
    debug_mode: Optional[bool] = Form(False),
    use_ifc_pipeline: Optional[bool] = Form(True),  # Default to new IFC pipeline
    save_intermediate_ifc: Optional[bool] = Form(False)  # Save IFC file for debugging
):
    """
    CityGMLファイル（.gml/.xml）を受け取り、STEPファイルを生成するAPI。
    Plateauの建物データに対応し、MultiSurfaceを賢くSolidに変換します。
    
    Enhanced Geometry Processing:
    - use_ifc_pipeline=True: 新しいIFC中間変換パイプライン（推奨、より安定）
    - use_ifc_pipeline=False: 従来のOpenCASCADE直接変換パイプライン
    - save_intermediate_ifc=True: デバッグ用にIFCファイルも保存
    
    Improved Error Reporting:
    - X-Error-Stage ヘッダーでエラー発生段階を特定
    - X-Pipeline-Type ヘッダーで使用されたパイプラインを表示
    - 幾何学検証とより詳細なエラーメッセージ
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。CityGML処理に必要です。")
    
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.gml') or 
                file.filename.lower().endswith('.xml') or
                file.filename.lower().endswith('.citygml')):
            raise HTTPException(status_code=400, detail="CityGMLファイル（.gml/.xml/.citygml）のみ対応です。")
        
        # ファイル内容を読み込み
        file_content = await file.read()
        
        # 処理オプションを設定
        options = CityGMLProcessingOptions(
            preferred_lod=preferred_lod or 2,
            min_building_area=min_building_area,
            max_building_count=max_building_count,
            tolerance=tolerance or 1e-6,
            export_individual_files=export_individual_files or False,
            debug_mode=debug_mode or True,  # Enable debug by default for better error reporting
            use_ifc_pipeline=use_ifc_pipeline if use_ifc_pipeline is not None else True,  # Use new IFC pipeline by default
            ifc_schema_version="IFC4",
            save_intermediate_ifc=save_intermediate_ifc or False
        )
        
        # CityGMLプロセッサーを初期化
        processor = CityGMLProcessor(options)
        
        # 出力パスを生成
        if export_individual_files:
            output_base = os.path.join(tempfile.mkdtemp(), f"citygml_buildings_{uuid.uuid4()}")
            output_path = output_base + ".step"  # ディレクトリ名の参照用
        else:
            output_path = os.path.join(tempfile.mkdtemp(), f"citygml_to_step_{uuid.uuid4()}.step")
        
        # CityGMLを処理してSTEPに変換
        result = processor.process_from_bytes(file_content, output_path)
        
        if not result.success:
            # より詳細なエラー情報を提供
            error_detail = {
                "message": result.error_message,
                "processing_stage": "unknown",
                "buildings_parsed": result.buildings_parsed,
                "buildings_processed": result.buildings_solidified,
                "parse_time": round(result.parse_time or 0, 3),
                "solidify_time": round(result.solidify_time or 0, 3),
                "export_time": round(result.export_time or 0, 3)
            }
            
            # エラーの段階を特定
            if result.parse_time and result.solidify_time is None:
                error_detail["processing_stage"] = "parsing"
            elif result.solidify_time and result.export_time is None:
                error_detail["processing_stage"] = "geometry_creation"
            elif result.export_time:
                error_detail["processing_stage"] = "step_export"
            
            raise HTTPException(
                status_code=400, 
                detail=f"CityGML変換に失敗しました: {result.error_message}",
                headers={
                    "X-Error-Stage": error_detail["processing_stage"],
                    "X-Buildings-Parsed": str(error_detail["buildings_parsed"]),
                    "X-Buildings-Processed": str(error_detail["buildings_processed"])
                }
            )
        
        if export_individual_files:
            # 個別ファイルの場合はZIPアーカイブとして返す
            import zipfile
            zip_path = output_path.replace('.step', '.zip')
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                building_dir = result.step_file_path
                if os.path.isdir(building_dir):
                    for root, dirs, files in os.walk(building_dir):
                        for file_name in files:
                            if file_name.endswith('.step'):
                                file_path = os.path.join(root, file_name)
                                zipf.write(file_path, file_name)
            
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=f"citygml_buildings_{uuid.uuid4()}.zip",
                headers={
                    "X-Buildings-Parsed": str(result.buildings_parsed),
                    "X-Buildings-Solidified": str(result.buildings_solidified),
                    "X-Solids-Created": str(result.solids_created),
                    "X-Processing-Time": str(round(result.total_time, 2))
                }
            )
        else:
            # 単一ファイルとして返す
            # 拡張されたレスポンスヘッダー（新しいIFCパイプライン情報を含む）
            response_headers = {
                "X-Buildings-Parsed": str(result.buildings_parsed),
                "X-Buildings-Solidified": str(result.buildings_solidified),
                "X-Processing-Time": str(round(result.total_time, 2)),
                "X-Parse-Time": str(round(result.parse_time or 0, 3)),
                "X-Solidify-Time": str(round(result.solidify_time or 0, 3)),
                "X-Export-Time": str(round(result.export_time or 0, 3)),
                "X-Pipeline-Type": "IFC" if options.use_ifc_pipeline else "Legacy"
            }
            
            # IFCパイプライン固有の情報を追加
            if hasattr(result, 'solidification_stats') and result.solidification_stats:
                if 'ifc_elements_created' in result.solidification_stats:
                    response_headers["X-IFC-Elements-Created"] = str(result.solidification_stats['ifc_elements_created'])
                if 'schema_version' in result.solidification_stats:
                    response_headers["X-IFC-Schema-Version"] = result.solidification_stats['schema_version']
            
            if hasattr(result, 'export_stats') and result.export_stats:
                if 'entities_exported' in result.export_stats:
                    response_headers["X-STEP-Entities-Exported"] = str(result.export_stats['entities_exported'])
                if 'file_size_bytes' in result.export_stats:
                    response_headers["X-STEP-File-Size"] = str(result.export_stats['file_size_bytes'])
            
            # Legacy統計情報（下位互換性のため）
            if hasattr(result, 'solids_created'):
                response_headers["X-Solids-Created"] = str(result.solids_created)
            if hasattr(result, 'shells_created'):
                response_headers["X-Shells-Created"] = str(result.shells_created)
            
            return FileResponse(
                path=result.step_file_path,
                media_type="application/step",
                filename=f"citygml_to_step_{uuid.uuid4()}.step",
                headers=response_headers
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")

# --- CityGML to BREP変換エンドポイント ---
@router.post("/api/citygml/to-brep")
async def convert_citygml_to_brep(
    file: UploadFile = File(...),
    preferred_lod: Optional[int] = Form(2),
    min_building_area: Optional[float] = Form(None),
    max_building_count: Optional[int] = Form(None),
    tolerance: Optional[float] = Form(1e-5),  # Optimized for building-scale geometry
    export_individual_files: Optional[bool] = Form(False),
    debug_mode: Optional[bool] = Form(False)
):
    """
    CityGMLファイル（.gml/.xml）を受け取り、BREPファイルを生成するAPI。
    Plateauの建物データに特化し、OpenCASCADE直接変換パイプラインを使用。
    
    Plateau Building Optimization:
    - tolerance=1e-5: 建物スケールに最適化された幾何学精度
    - preferred_lod=2: LoD2建物形状データに最適
    - export_individual_files=True: 建物ごとの個別BREPファイル出力
    
    BREP Format Features:
    - CADソフトウェアでの高精度3Dモデル利用
    - OpenCASCADE直接出力による高い形状精度
    - Solid、Shell、Compound形状の完全サポート
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。CityGML処理に必要です。")
    
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.gml') or 
                file.filename.lower().endswith('.xml') or
                file.filename.lower().endswith('.citygml')):
            raise HTTPException(status_code=400, detail="CityGMLファイル（.gml/.xml/.citygml）のみ対応です。")
        
        # ファイル内容を読み込み
        file_content = await file.read()
        
        # 処理オプションを設定（BREP出力用にOpenCASCADEパイプライン強制）
        options = CityGMLProcessingOptions(
            preferred_lod=preferred_lod or 2,
            min_building_area=min_building_area,
            max_building_count=max_building_count,
            tolerance=tolerance or 1e-5,  # Building-scale optimized tolerance
            export_individual_files=export_individual_files or False,
            debug_mode=debug_mode or True,  # Enable debug by default for better error reporting
            use_ifc_pipeline=False,  # Force legacy OpenCASCADE pipeline for BREP export
            ifc_schema_version="IFC4",  # Not used but kept for compatibility
            save_intermediate_ifc=False  # Not applicable for BREP export
        )
        
        # CityGMLプロセッサーを初期化
        processor = CityGMLProcessor(options)
        
        # 出力パスを生成
        if export_individual_files:
            output_base = os.path.join(tempfile.mkdtemp(), f"citygml_buildings_{uuid.uuid4()}")
            output_path = output_base + ".brep"  # ディレクトリ名の参照用
        else:
            output_path = os.path.join(tempfile.mkdtemp(), f"citygml_to_brep_{uuid.uuid4()}.brep")
        
        # CityGMLを処理してBREPに変換
        result = processor.process_to_brep(file_content, output_path)
        
        if not result.success:
            # より詳細なエラー情報を提供
            error_detail = {
                "message": result.error_message,
                "processing_stage": "unknown",
                "buildings_parsed": result.buildings_parsed,
                "buildings_processed": result.buildings_solidified,
                "parse_time": round(result.parse_time or 0, 3),
                "solidify_time": round(result.solidify_time or 0, 3),
                "export_time": round(result.export_time or 0, 3)
            }
            
            # エラーの段階を特定
            if result.parse_time and result.solidify_time is None:
                error_detail["processing_stage"] = "parsing"
            elif result.solidify_time and result.export_time is None:
                error_detail["processing_stage"] = "geometry_creation"
            elif result.export_time:
                error_detail["processing_stage"] = "brep_export"
            
            raise HTTPException(
                status_code=400, 
                detail=f"CityGML to BREP変換に失敗しました: {result.error_message}",
                headers={
                    "X-Error-Stage": error_detail["processing_stage"],
                    "X-Buildings-Parsed": str(error_detail["buildings_parsed"]),
                    "X-Buildings-Processed": str(error_detail["buildings_processed"])
                }
            )
        
        if export_individual_files:
            # 個別ファイルの場合はZIPアーカイブとして返す
            import zipfile
            zip_path = output_path.replace('.brep', '.zip')
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                building_dir = result.brep_file_path
                if os.path.isdir(building_dir):
                    for root, dirs, files in os.walk(building_dir):
                        for file_name in files:
                            if file_name.endswith('.brep'):
                                file_path = os.path.join(root, file_name)
                                zipf.write(file_path, file_name)
            
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename=f"citygml_buildings_{uuid.uuid4()}.zip",
                headers={
                    "X-Buildings-Parsed": str(result.buildings_parsed),
                    "X-Buildings-Solidified": str(result.buildings_solidified),
                    "X-Solids-Created": str(result.solids_created),
                    "X-Shells-Created": str(result.shells_created),
                    "X-Processing-Time": str(round(result.total_time, 2)),
                    "X-Pipeline-Type": "OpenCASCADE-Direct"
                }
            )
        else:
            # 単一BREPファイルとして返す
            response_headers = {
                "X-Buildings-Parsed": str(result.buildings_parsed),
                "X-Buildings-Solidified": str(result.buildings_solidified),
                "X-Solids-Created": str(result.solids_created),
                "X-Shells-Created": str(result.shells_created),
                "X-Processing-Time": str(round(result.total_time, 2)),
                "X-Parse-Time": str(round(result.parse_time or 0, 3)),
                "X-Solidify-Time": str(round(result.solidify_time or 0, 3)),
                "X-Export-Time": str(round(result.export_time or 0, 3)),
                "X-Pipeline-Type": "OpenCASCADE-Direct"
            }
            
            # BREP export固有の統計情報を追加
            if hasattr(result, 'export_stats') and result.export_stats:
                if 'shapes_exported' in result.export_stats:
                    response_headers["X-BREP-Shapes-Exported"] = str(result.export_stats['shapes_exported'])
                if 'file_size_bytes' in result.export_stats:
                    response_headers["X-BREP-File-Size"] = str(result.export_stats['file_size_bytes'])
            
            return FileResponse(
                path=result.brep_file_path,
                media_type="application/octet-stream",
                filename=f"citygml_to_brep_{uuid.uuid4()}.brep",
                headers=response_headers
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")

# --- CityGML検証エンドポイント ---
@router.post("/api/citygml/validate")
async def validate_citygml_file(file: UploadFile = File(...)):
    """
    CityGMLファイルの検証を行い、建物数や処理可能性を確認するAPI。
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。")
    
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.gml') or 
                file.filename.lower().endswith('.xml') or
                file.filename.lower().endswith('.citygml')):
            raise HTTPException(status_code=400, detail="CityGMLファイル（.gml/.xml/.citygml）のみ対応です。")
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.gml', delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            # 検証処理
            processor = CityGMLProcessor()
            validation_result = processor.validate_citygml_file(temp_file.name)
            
            # 一時ファイルを削除
            os.unlink(temp_file.name)
            
            return {
                "filename": file.filename,
                "file_size": len(content),
                "is_valid": validation_result["is_valid"],
                "building_count": validation_result.get("building_count", 0),
                "parsing_stats": validation_result.get("parsing_stats"),
                "error_message": validation_result.get("error_message"),
                "estimated_processing_time": processor.estimate_processing_time(
                    validation_result.get("building_count", 0)
                ) if validation_result["is_valid"] else None
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"検証エラー: {str(e)}")

# --- ヘルスチェック ---
@router.get("/api/health")
async def api_health_check():
    # CityGMLプロセッサーの機能情報を取得
    capabilities = {}
    if OCCT_AVAILABLE:
        try:
            processor = CityGMLProcessor()
            capabilities = processor.get_processing_capabilities()
        except:
            capabilities = {"error": "Could not initialize CityGML processor"}
    
    # IFC処理能力をチェック
    ifc_capabilities = {}
    try:
        import ifcopenshell
        ifc_capabilities = {
            "ifcopenshell_available": True,
            "ifcopenshell_version": getattr(ifcopenshell, '__version__', 'unknown'),
            "supported_schemas": ["IFC4", "IFC2X3"],
            "geometry_processing": True,
            "step_export": True
        }
    except ImportError:
        ifc_capabilities = {
            "ifcopenshell_available": False,
            "error": "ifcopenshell not available"
        }
    
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "version": "2.3.0",  # Added BREP export support for Plateau buildings
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["step", "brep", "gml", "xml", "citygml"] if OCCT_AVAILABLE else [],
        "citygml_capabilities": capabilities,
        "ifc_capabilities": ifc_capabilities,
        "conversion_pipelines": {
            "legacy_opencascade": OCCT_AVAILABLE,
            "ifc_intermediate": ifc_capabilities.get("ifcopenshell_available", False),
            "brep_export": OCCT_AVAILABLE  # Direct BREP export for CAD software
        },
        "geometry_features": {
            "surface_reconstruction": True,
            "multi_lod_support": True,
            "building_classification": True,
            "geometry_validation": True,
            "error_reporting": "enhanced",
            "brep_export": OCCT_AVAILABLE,
            "individual_building_export": True
        },
        "plateau_support": {
            "optimized_for_plateau": True,
            "lod_filtering": [0, 1, 2],
            "building_scale_tolerance": "1e-5",
            "individual_brep_export": True,
            "batch_processing": True
        }
    }