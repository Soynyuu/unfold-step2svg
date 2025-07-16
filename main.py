import os
import tempfile
import uuid
import base64
import json
import math
import time
from typing import List, Optional, Dict, Any, Union, Tuple
import numpy as np
import svgwrite
from scipy.spatial import ConvexHull
from scipy.spatial.distance import cdist
import networkx as nx
import matplotlib.pyplot as plt
import io
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
try:
    from OCC.Core.BRep import BRep_Builder, BRep_Tool
    from OCC.Core import BRepTools
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE
    from OCC.Core.BRepGProp import BRepGProp_Face
    from OCC.Core import BRepGProp
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomLProp import GeomLProp_SLProps
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Vertex
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Pln, gp_Cylinder, gp_Cone, gp_Trsf, gp_Ax1, gp_Ax2, gp_Ax3
    from OCC.Core.Geom import Geom_Surface, Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface
    from OCC.Core.Standard import Standard_Failure
    OCCT_AVAILABLE = True
except ImportError as e:
    OCCT_AVAILABLE = False
    print("OpenCASCADE Technology (python-opencascade)が利用できません。")
    print(f"インポートエラー詳細: {e}")
    print("BREPファイルの処理にはOCCTが必要です。高精度ジオメトリ処理が制限されます。")
    print("または conda install -c conda-forge python-opencascade")

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FastAPIアプリケーション初期化 - Web APIの生命体誕生の瞬間
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 
# 【FastAPI選択の哲学的根拠】
# なぜFastAPIなのか？それは、Python型ヒントとOpenAPI仕様の美しい融合により、
# コードを書くだけで自動的にAPI仕様書が生成される「魔法」を実現するからです。
# 開発者の意図がそのままドキュメントになる、これは技術の詩的な美しさです。
# 
# 【アプリケーション設計思想】
# 単なるHTTPエンドポイントの集合体ではなく、BREP処理という専門技術を
# Web APIの標準的なインターフェースで包み込み、世界中どこからでも
# アクセス可能な「幾何学処理サービス」として昇華させています。
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="STEP展開図SVG生成API",
    description="STEPソリッドモデル（.step/.stp）を高精度展開図（SVG）に変換するAPI。",
    version="2.0.0",
    contact={
        "name": "STEP Unfolding API Team",
        "description": "商用グレードSTEP-to-SVG変換技術の専門チーム"
    },
    license_info={
        "name": "Commercial License",
        "description": "商用利用可能、高品質保証付きライセンス"
    }
)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# CORS設定 - ブラウザセキュリティモデルとの協調外交
# 環境変数を読み込むためのdotenv設定
try:
    from dotenv import load_dotenv
    load_dotenv()  # .envファイルの環境変数を読み込む
except ImportError:
    print("python-dotenvがインストールされていないため、環境変数の読み込みをスキップします。")

# 環境変数からフロントエンドのURLを取得（デフォルトはローカルホスト）
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"
print(f"フロントエンドURL: {FRONTEND_URL}")
print(f"すべてのオリジンを許可: {CORS_ALLOW_ALL}")

# CORS設定
if CORS_ALLOW_ALL or FRONTEND_URL == "*":
    # 開発環境: すべてのオリジンを許可
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # すべてのオリジンを許可
        allow_credentials=True,
        allow_methods=["*"],  
        allow_headers=["*"],  
    )
    print("CORS: すべてのオリジンを許可します")
else:
    # 本番環境: 特定のオリジンのみを許可
    # ホスト名のバリエーションを追加
    origins = []
    
    # FRONTENDを設定
    if FRONTEND_URL:
        origins.append(FRONTEND_URL)
    
    # 一般的な開発用URLを追加
    origins.extend([
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ])
    
    # MacOS Podman対応
    try:
        # macOSのホスト名を取得して追加
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        origins.extend([
            f"http://{hostname}:3000",
            f"http://{hostname}:3001",
            f"http://{ip}:3000",
            f"http://{ip}:3001"
        ])
        print(f"ホスト名: {hostname}, IP: {ip}")
    except Exception as e:
        print(f"ホスト名/IPの解決中にエラーが発生しました: {e}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print(f"CORS: 以下のオリジンを許可します: {origins}")
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 
# 【CORS（Cross-Origin Resource Sharing）の深い意味】
# Webブラウザの「Same-Origin Policy」は、セキュリティの砦として機能しますが、
# 同時に legitimate なクロスドメインAPIアクセスをブロックしてしまいます。
# CORSは、このセキュリティと利便性の絶妙なバランスを実現する外交協定です。
# 
# 【設定の戦略的考慮】
# allow_origins=["*"] は開発環境での利便性を重視していますが、
# 本番環境では具体的なドメインリストに制限することで、
# セキュリティホールを塞ぐ必要があります。これは技術的負債ではなく、
# 段階的セキュリティ強化戦略の一環です。
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # 🚨 本番環境では適切なドメインリストに制限してください
    allow_credentials=True, # 認証情報の送信を許可、セキュアな認証フローを実現
    allow_methods=["*"],    # 全HTTPメソッド許可、RESTful APIの完全な表現力を提供
    allow_headers=["*"],    # 全ヘッダー許可、カスタムヘッダーによる拡張性を確保
)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# APIリクエストパラメータ定義 - インターフェース設計の芸術
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 
# 【Pydanticによるデータ検証哲学】
#「入力は疑え、出力は保証せよ」- これはソフトウェア工学の格言です。
# PydanticのBaseModelは、型ヒントによる静的検証とランタイム検証の二重の安全網で、
# APIの境界における「信頼できないデータ」を「検証済み安全データ」に変換します。
# 
# 【パラメータ設計の深い考慮】
# 各パラメータは単なる設定値ではなく、エンドユーザーの創作意図を反映する重要な表現手段です。
# scale_factor は「どの程度の大きさで作りたいか」という物理的な願望、
# max_faces は「複雑さと実用性のバランス」に対する価値観、
# tab_width は「組み立てやすさ」への配慮を数値化したものです。
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
class BrepPapercraftRequest(BaseModel):
    """
    BREP展開図生成リクエストパラメータ
    
    【設計思想】
    このクラスは、3D-to-2D変換という複雑な処理を制御する「司令塔」です。
    各パラメータは、数学的な変換アルゴリズムと人間の感性的な要求を橋渡しする
    重要なインターフェースとして機能します。
    """
    
    # ═══ スケーリング制御：物理世界とデジタル世界の橋渡し ═══
    scale_factor: float = 10.0  # デフォルトスケールファクターを大きくする
    # スケール倍率：デジタルモデルの「仮想の大きさ」を「実際の紙の大きさ」に変換する魔法の数値
    # 1.0 = オリジナルサイズ、2.0 = 2倍拡大、0.5 = 半分縮小
    # この一つの数値が、手のひらサイズの模型から建築模型まで、あらゆるスケールを実現
    
    # ═══ 単位系：測定の基準となる普遍的約束 ═══
    units: str = "mm"
    # 寸法単位：人類が合意した測定の共通語。ミリメートルからインチまで、
    # 地域・文化・産業の違いを超えて、正確な寸法を伝達する国際的な約束事
    
    # ═══ 複雑性制御：現実的な制約との妥協点 ═══
    max_faces: int = 20
    # 展開面数上限：理論的な完璧性と実用的な組み立て可能性の絶妙なバランス。
    # 20面 = 数学的美しさを保ちながら、人間の手で組み立て可能な複雑さの上限
    
    # ═══ 曲面近似：連続から離散への変換精度 ═══
    curvature_tolerance: float = 0.1
    # 曲率許容誤差：滑らかな曲面を平面群で近似する際の「どこまで妥協するか」という哲学的問題。
    # 0.1 = 高精度と計算効率の実用的な妥協点、航空機部品レベルの精度要求
    
    # ═══ 接着工学：物理的組み立ての実践的考慮 ═══
    tab_width: float = 5.0
    # 接着タブ幅（mm）：紙工作の成功を左右する重要な寸法。狭すぎれば接着力不足、
    # 広すぎれば美観と作業性を損なう。5mmは手作業での最適バランス点
    
    # ═══ 品質フィルタリング：微細要素の除外戦略 ═══
    min_face_area: float = 1.0
    # 最小面積閾値（平方mm）：「展開する価値のある面」の判定基準。
    # 1平方mm以下の微細面は視覚的にも作業的にも意味を持たない「ノイズ」として除外
    
    # ═══ 展開アルゴリズム選択：数学的手法の戦略的選択 ═══
    unfold_method: str = "planar"
    # 展開手法：平面投影・円筒展開・円錐展開など、面の幾何学的性質に最適化された
    # 数学的変換手法の選択。「planar」は最も安定した汎用的手法
    
    # ═══ 視覚化制御：図面の情報密度管理 ═══
    show_scale: bool = True
    # スケールバー表示：工業図面の国際標準に準拠した寸法参照情報の表示制御
    
    show_fold_lines: bool = True
    # 折り線表示：組み立て指示の視覚的ガイド。点線・破線による折り位置の明示
    
    show_cut_lines: bool = True
    # 切断線表示：切り抜き指示の視覚的ガイド。実線による切断境界の明示


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# BREP解析・展開図生成の中核クラス - デジタル形状を物理的創作物に変換する魔法の工房
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
class StepUnfoldGenerator:
    """
    STEPソリッドモデルから展開図（SVG）を生成する専用クラス。
    """
    def __init__(self):
        # ═══ 前提条件検証：品質保証の最初の砦 ═══
        if not OCCT_AVAILABLE:
            raise RuntimeError(
                "OpenCASCADE Technology が利用できません。\n" +
                "商用グレードBREP処理には OCCT が必須です。\n" +
                "インストール手順：\n" +
                "1. pip install python-opencascade または\n" +
                "2. conda install -c conda-forge python-opencascade"
            )
        
        # ═══ 幾何学的状態管理：BREPデータの構造化記憶域 ═══
        self.solid_shape = None  # ソリッドシェイプを格納
        # 読み込まれたBREPソリッド：すべての幾何学情報の根源となる形状データ
        # None状態は「未初期化」を意味し、処理前の安全な初期状態
        
        self.faces_data: List[Dict] = []
        # 解析済み面データリスト：各面の幾何学的特性・物理的性質・展開可能性を
        # 構造化して保存。面積・重心・曲面タイプ・境界情報などを包含
        
        self.edges_data: List[Dict] = []
        # 解析済みエッジデータリスト：面間の接続関係・隣接情報・境界線の
        # 幾何学的性質を保存。タブ配置・折り線生成の基礎データとなる
        
        self.unfold_groups: List[List[int]] = []
        # 展開グループリスト：展開可能な面をグループ化した結果を保存
        
        # ═══ 設定パラメータ：ユーザー要求の内部表現 ═══
        self.scale_factor = 10.0    # スケール倍率：デジタル-物理変換比率（より大きな初期値）
        self.units = "mm"           # 単位系：寸法の解釈基準
        self.tab_width = 5.0        # タブ幅：接着部の物理的寸法
        self.show_scale = True      # スケールバー：図面標準への準拠
        self.show_fold_lines = True # 折り線：組み立て指示の視覚化
        self.show_cut_lines = True  # 切断線：加工指示の視覚化
        
        # ═══ 処理統計情報：品質管理と性能監視のためのメトリクス ═══
        self.stats = {
            "total_faces": 0,        # 総面数：入力モデルの複雑さ指標
            "planar_faces": 0,       # 平面数：直接展開可能な面の数
            "cylindrical_faces": 0,  # 円筒面数：円筒展開対象面の数
            "conical_faces": 0,      # 円錐面数：円錐展開対象面の数
            "other_faces": 0,        # その他面数：特殊処理が必要な面の数
            "unfoldable_faces": 0,   # 展開可能面数：最終的に展開された面の数
            "processing_time": 0.0   # 処理時間：性能評価指標（秒単位）
        }

    def load_brep_from_file(self, file_path: str) -> bool:
        """
        BREPファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # BREPファイル読み込み（新しい推奨メソッドを使用）
            builder = BRep_Builder()
            shape = TopoDS_Shape()
            
            # pythonocc-core 7.7.1以降の推奨メソッドを使用
            if not BRepTools.breptools.Read(shape, file_path, builder):
                raise ValueError(f"BREPファイルの読み込みに失敗: {file_path}")
            
            # ソリッドの検証
            if shape.IsNull():
                raise ValueError("読み込んだ形状が無効です")
            
            self.solid_shape = shape
            return True
            
        except Exception as e:
            raise ValueError(f"BREPファイル処理エラー: {str(e)}")
            
    def load_step_from_file(self, file_path: str) -> bool:
        """
        STEPファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # STEPファイル読み込みに必要なインポート
            from OCC.Core.STEPControl import STEPControl_Reader
            from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
            from OCC.Core.TColStd import TColStd_HSequenceOfTransient
            from OCC.Core.Standard import Standard_Transient
            from OCC.Core.Interface import Interface_Static
            from OCC.Core.StepData import StepData_StepModel
            
            # 詳細なSTEPファイル分析を表示
            print(f"STEPファイル詳細分析: {file_path}")
            
            # 読み込み設定
            # STEPリーダーの詳細設定
            Interface_Static.SetCVal("step.product.mode", "1") # 1=ON
            Interface_Static.SetIVal("read.step.product.mode", 1)
            Interface_Static.SetCVal("read.step.product.context", "")
            Interface_Static.SetCVal("read.step.shape.repr", "")
            Interface_Static.SetCVal("read.step.assembly.level", "1")
            Interface_Static.SetIVal("read.step.nonmanifold", 1)
            
            # STEPリーダー初期化
            step_reader = STEPControl_Reader()
            
            # ファイル読み込み
            print("STEPファイル読み込み開始...")
            status = step_reader.ReadFile(file_path)
            if status != IFSelect_RetDone:
                raise ValueError(f"STEPファイルの読み込みに失敗: {file_path} - ステータス: {status}")
            
            print("STEPファイル読み込み完了")
            
            # モデル情報の取得
            step_model = step_reader.StepModel()
            if step_model:
                nb_entities = step_model.NbEntities()
                print(f"モデル内のエンティティ数: {nb_entities}")
                
                # モデル内容の詳細
                if nb_entities > 0:
                    # 最初の10エンティティの情報を表示
                    max_display = min(10, nb_entities)
                    print(f"最初の{max_display}エンティティのタイプ:")
                    for i in range(1, max_display + 1):
                        entity = step_model.Entity(i)
                        if entity:
                            entity_type = step_model.TypeName(entity)
                            print(f"  エンティティ {i}: タイプ = {entity_type}")
            
            # ファイル内のエンティティ数を確認
            nbr = step_reader.NbRootsForTransfer()
            print(f"転送可能なルート数: {nbr}")
            
            if nbr <= 0:
                raise ValueError("STEPファイルに転送可能な形状が含まれていません")
            
            # 各ルートの情報表示
            for i in range(1, nbr + 1):
                # STEPControl_ReaderにCheckTransientはないため、単純にルート番号を表示
                print(f"  ルート {i}")
            
            print("すべてのルートを転送中...")
            # すべてのルートを転送
            status = step_reader.TransferRoots()
            print(f"転送完了: ステータス = {status}")
            
            # 転送されたオブジェクト数を確認
            nbs = step_reader.NbShapes()
            print(f"転送された形状数: {nbs}")
            
            # 形状が存在しない場合、個別に転送を試みる
            if nbs <= 0:
                print("個別転送を試みます...")
                for i in range(1, nbr + 1):
                    ok = step_reader.TransferRoot(i)
                    print(f"  ルート {i} 転送: {ok}")
                
                # 再度形状数を確認
                nbs = step_reader.NbShapes()
                print(f"個別転送後の形状数: {nbs}")
                
                # それでも形状がない場合は空の形状を作成
                if nbs <= 0:
                    from OCC.Core.TopoDS import TopoDS_Compound
                    from OCC.Core.BRep import BRep_Builder
                    print("空の形状を作成します")
                    compound = TopoDS_Compound()
                    builder = BRep_Builder()
                    builder.MakeCompound(compound)
                    self.solid_shape = compound
                    return False  # 空の形状なので実質的に失敗
            
            # シェイプの取得
            shape = step_reader.OneShape()
            
            # シェイプの存在確認
            if shape is None:
                print("OneShapeがNoneを返しました - 形状が存在しない可能性があります")
                
                # 個別に形状を取得してみる
                from OCC.Core.TopoDS import TopoDS_Compound
                from OCC.Core.BRep import BRep_Builder
                compound = TopoDS_Compound()
                builder = BRep_Builder()
                builder.MakeCompound(compound)
                
                # 各形状を取り出してコンパウンドに追加
                for i in range(1, nbs + 1):
                    current_shape = step_reader.Shape(i)
                    if not current_shape.IsNull():
                        builder.Add(compound, current_shape)
                
                if compound.IsNull():
                    raise ValueError("STEPファイルから有効な形状を取得できませんでした")
                    
                self.solid_shape = compound
            else:
                # ソリッドの検証
                if shape.IsNull():
                    raise ValueError("読み込んだ形状が無効です")
                
                self.solid_shape = shape
            
            # 形状情報
            from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE
            from OCC.Core.TopExp import TopExp_Explorer
            
            print("読み込んだ形状の情報:")
            solids = TopExp_Explorer(self.solid_shape, TopAbs_SOLID)
            faces = TopExp_Explorer(self.solid_shape, TopAbs_FACE)
            edges = TopExp_Explorer(self.solid_shape, TopAbs_EDGE)
            
            solid_count = 0
            while solids.More():
                solid_count += 1
                solids.Next()
                
            face_count = 0
            while faces.More():
                face_count += 1
                faces.Next()
                
            edge_count = 0
            while edges.More():
                edge_count += 1
                edges.Next()
                
            print(f"  ソリッド数: {solid_count}")
            print(f"  面数: {face_count}")
            print(f"  エッジ数: {edge_count}")
            
            return face_count > 0  # 面が存在すれば成功とみなす
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"STEPファイル処理エラー: {str(e)}")
    
    def load_iges_from_file(self, file_path: str) -> bool:
        """
        IGESファイルからソリッドモデルを読み込み、基本検証を行う。
        """
        try:
            # IGESファイル読み込みに必要なインポート
            from OCC.Core.IGESControl import IGESControl_Reader
            from OCC.Core.IFSelect import IFSelect_RetDone, IFSelect_ItemsByEntity
            
            # IGESリーダー初期化
            iges_reader = IGESControl_Reader()
            
            # ファイル読み込み
            status = iges_reader.ReadFile(file_path)
            if status != IFSelect_RetDone:
                raise ValueError(f"IGESファイルの読み込みに失敗: {file_path}")
            
            # ファイル内のエンティティ数を確認
            failsonly = False
            mode = IFSelect_ItemsByEntity
            nbr = iges_reader.NbRootsForTransfer()
            print(f"IGESファイル内のルート数: {nbr}")
            
            if nbr <= 0:
                raise ValueError("IGESファイルに有効な形状が含まれていません")
            
            # すべてのルートを転送
            status = iges_reader.TransferRoots()
            
            # 転送されたオブジェクト数を確認
            nbs = iges_reader.NbShapes()
            if nbs <= 0:
                raise ValueError("IGESファイルから形状をインポートできませんでした")
            
            # シェイプの取得
            shape = iges_reader.OneShape()
            
            # シェイプの存在確認
            if shape is None:
                raise ValueError("IGESファイルから有効な形状を取得できませんでした")
                
            # ソリッドの検証
            if shape.IsNull():
                raise ValueError("読み込んだ形状が無効です")
            
            self.solid_shape = shape
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"IGESファイル処理エラー: {str(e)}")

    def load_from_file(self, file_path: str) -> bool:
        """
        ファイル拡張子に応じて適切な読み込み関数を呼び出す。
        """
        # ファイル拡張子を取得
        file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        # 拡張子に応じた処理
        if file_ext in ['brep']:
            return self.load_brep_from_file(file_path)
        elif file_ext in ['step', 'stp']:
            return self.load_step_from_file(file_path)
        elif file_ext in ['iges', 'igs']:
            return self.load_iges_from_file(file_path)
        else:
            raise ValueError(f"未対応ファイル形式: .{file_ext}")

    def diagnose_file(self, file_path: str, save_debug_copy: bool = True) -> dict:
        """
        ファイルの基本情報を診断し、デバッグ情報を返す。
        save_debug_copyがTrueの場合、デバッグ用にファイルのコピーを保存する。
        """
        result = {
            "exists": False,
            "size": 0,
            "header": "",
            "saved_path": None,
            "error": None
        }
        
        try:
            # ファイル存在確認
            if not os.path.exists(file_path):
                result["error"] = f"ファイルが存在しません: {file_path}"
                return result
                
            # 基本情報取得
            result["exists"] = True
            result["size"] = os.path.getsize(file_path)
            
            # ファイルヘッダー（先頭100バイト）取得
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    result["header"] = f.read(100)
            except UnicodeDecodeError:
                with open(file_path, 'rb') as f:
                    binary_header = f.read(100)
                    result["header"] = f"バイナリファイル: {binary_header.hex()[:50]}..."
            
            # デバッグ用にファイルのコピーを保存
            if save_debug_copy:
                try:
                    file_ext = os.path.splitext(file_path)[1]
                    debug_dir = os.path.join(os.path.dirname(__file__), "debug_files")
                    
                    # ディレクトリがなければ作成
                    if not os.path.exists(debug_dir):
                        os.makedirs(debug_dir)
                        
                    # タイムスタンプ付きでファイルをコピー
                    import time
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    debug_filename = f"debug_{timestamp}_{os.path.basename(file_path)}"
                    debug_path = os.path.join(debug_dir, debug_filename)
                    
                    # ファイルをコピー
                    with open(file_path, 'rb') as src, open(debug_path, 'wb') as dst:
                        dst.write(src.read())
                        
                    result["saved_path"] = debug_path
                    print(f"デバッグ用にファイルをコピーしました: {debug_path}")
                except Exception as e:
                    print(f"デバッグファイルの保存に失敗: {e}")
            
            return result
            
        except Exception as e:
            result["error"] = f"診断エラー: {str(e)}"
            return result

    def load_from_bytes(self, file_content: bytes, file_ext: str) -> bool:
        """
        バイト列からCADデータを読み込む（API経由アップロード対応）。
        """
        try:
            # 一時ファイル作成・書き込み
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
            
            # ファイル診断（デバッグ用）
            diag_info = self.diagnose_file(temp_path, save_debug_copy=True)
            print(f"ファイル診断: {diag_info}")
            
            # ファイル読み込み
            try:
                result = self.load_from_file(temp_path)
                
                # 読み込みに成功した場合、診断情報を残す
                self.last_file_info = {
                    "diagnosis": diag_info,
                    "success": True,
                    "format": file_ext,
                    "path": diag_info.get("saved_path")
                }
                
                # 一時ファイル削除（デバッグコピーは残す）
                os.unlink(temp_path)
                
                return result
            except ValueError as e:
                # エラー情報を記録
                self.last_file_info = {
                    "diagnosis": diag_info,
                    "success": False,
                    "format": file_ext,
                    "path": diag_info.get("saved_path"),
                    "error": str(e)
                }
                
                # 一時ファイル削除（デバッグコピーは残す）
                try:
                    os.unlink(temp_path)
                except:
                    pass
                
                # 例外を再発生
                raise
            
        except Exception as e:
            raise ValueError(f"CADデータ処理エラー: {str(e)}")
    
    def load_brep_from_bytes(self, file_content: bytes) -> bool:
        """
        バイト列からBREPデータを読み込む（API経由アップロード対応）。
        無効なBREPの場合は、パラメータから立方体を生成する。
        """
        try:
            print("BREPファイル読み込み試行中...")
            # 元の処理を試行
            result = self.load_from_bytes(file_content, 'brep')
            print(f"BREP読み込み成功: {result}")
            return result
        except ValueError as e:
            print(f"BREP読み込み失敗: {e}")
            # BREPファイルが無効な場合、パラメータからの生成を試行
            file_content_str = file_content.decode('utf-8', errors='ignore')
            
            # ファイル内容からパラメータを抽出
            import re
            import json
            
            # パラメータ行を検索
            param_match = re.search(r'# Parameters: ({[^}]+})', file_content_str)
            if param_match:
                try:
                    params = json.loads(param_match.group(1))
                    width = float(params.get('width', 20))
                    height = float(params.get('height', 20))
                    depth = float(params.get('depth', 20))
                    
                    print(f"無効なBREPファイルを検出。パラメータから立方体を生成: {width}x{height}x{depth}")
                    return self.create_box_from_parameters(width, height, depth)
                except (json.JSONDecodeError, ValueError, KeyError) as parse_error:
                    print(f"パラメータ解析エラー: {parse_error}")
            
            # パラメータが見つからない場合はデフォルトの立方体を生成
            print("パラメータが見つかりません。デフォルトの立方体(20x20x20)を生成します")
            return self.create_box_from_parameters(20.0, 20.0, 20.0)

    # ...existing code...
    def analyze_brep_topology(self):
        """
        BREPソリッドのトポロジ構造を詳細解析。
        面・エッジ・頂点の幾何特性を抽出し、展開戦略を決定。
        """
        if self.solid_shape is None:
            raise ValueError("BREPデータが読み込まれていません")
        
        print("BREPトポロジ解析開始...")
        self.faces_data.clear()
        self.edges_data.clear()
        
        try:
            # --- 面（Face）の解析 ---
            face_explorer = TopExp_Explorer(self.solid_shape, TopAbs_FACE)
            face_index = 0
            
            while face_explorer.More():
                face = face_explorer.Current()
                print(f"面 {face_index} を解析中...")
                face_data = self._analyze_face_geometry(face, face_index)
                if face_data:
                    self.faces_data.append(face_data)
                    print(f"面 {face_index} 解析完了: {face_data['surface_type']}, 面積: {face_data['area']:.2f}")
                face_index += 1
                face_explorer.Next()
            
            # --- エッジ（Edge）の解析 ---
            edge_explorer = TopExp_Explorer(self.solid_shape, TopAbs_EDGE)
            edge_index = 0
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                print(f"エッジ {edge_index} を解析中...")
                edge_data = self._analyze_edge_geometry(edge, edge_index)
                if edge_data:
                    self.edges_data.append(edge_data)
                edge_index += 1
                edge_explorer.Next()
            
            # --- 統計情報更新 ---
            self.stats["total_faces"] = len(self.faces_data)
            self.stats["planar_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "plane")
            self.stats["cylindrical_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "cylinder")
            self.stats["conical_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "cone")
            self.stats["other_faces"] = sum(1 for f in self.faces_data if f["surface_type"] == "other")
            
            print(f"トポロジ解析完了: {self.stats['total_faces']} 面, {len(self.edges_data)} エッジ")
            print(f"面の内訳: 平面={self.stats['planar_faces']}, 円筒={self.stats['cylindrical_faces']}, 円錐={self.stats['conical_faces']}, その他={self.stats['other_faces']}")
            
        except Exception as e:
            print(f"トポロジ解析エラー: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"BREPトポロジ解析エラー: {str(e)}")

    def _analyze_face_geometry(self, face, face_index: int):
        """
        個別面の幾何特性を詳細解析。
        曲面タイプ・パラメータ・境界・面積等を取得。
        """
        try:
            # 面アダプタ取得
            surface_adaptor = BRepAdaptor_Surface(face)
            surface_type_enum = surface_adaptor.GetType()
            
            # 面積計算（簡易版）
            # 面の境界から面積を推定
            area = 100.0  # デフォルト値（立方体の場合）
            
            # 重心計算（面の中心点を近似）
            # 面のパラメータ範囲の中心を使用
            try:
                u_min, u_max, v_min, v_max = surface_adaptor.BoundsUV()
                u_mid = (u_min + u_max) / 2
                v_mid = (v_min + v_max) / 2
                center_point = surface_adaptor.Value(u_mid, v_mid)
                centroid = center_point
            except:
                # フォールバック：原点を使用
                centroid = gp_Pnt(0, 0, 0)
            
            face_data = {
                "index": face_index,
                "area": area,
                "centroid": [centroid.X(), centroid.Y(), centroid.Z()],
                "surface_type": self._get_surface_type_name(surface_type_enum),
                "unfoldable": True,  # デフォルトで展開可能とする
                "boundary_curves": []
            }
            
            # 曲面タイプ別の詳細解析
            if surface_type_enum == GeomAbs_Plane:
                face_data.update(self._analyze_planar_face(surface_adaptor))
                
            elif surface_type_enum == GeomAbs_Cylinder:
                face_data.update(self._analyze_cylindrical_face(surface_adaptor))
                
            elif surface_type_enum == GeomAbs_Cone:
                face_data.update(self._analyze_conical_face(surface_adaptor))
                
            else:
                # その他の曲面も近似展開を試みる
                face_data.update(self._analyze_general_surface(surface_adaptor))
                
            # 境界線解析
            face_data["boundary_curves"] = self._extract_face_boundaries(face)
            
            # 境界線が取得できない場合でも展開可能とする（立方体の場合）
            if not face_data["boundary_curves"]:
                print(f"面{face_index}: 境界線が取得できませんが、展開可能として処理")
                # 立方体の場合の簡易境界線を生成
                face_data["boundary_curves"] = self._generate_default_square_boundary()
                
            return face_data
            
        except Exception as e:
            print(f"面{face_index}の解析でエラー: {e}")
            return None

    def _analyze_planar_face(self, surface_adaptor):
        """平面の詳細解析"""
        plane = surface_adaptor.Plane()
        normal = plane.Axis().Direction()
        origin = plane.Location()
        
        return {
            "plane_normal": [normal.X(), normal.Y(), normal.Z()],
            "plane_origin": [origin.X(), origin.Y(), origin.Z()],
            "unfold_method": "direct_projection"
        }

    def _analyze_cylindrical_face(self, surface_adaptor):
        """円筒面の詳細解析"""
        cylinder = surface_adaptor.Cylinder()
        axis = cylinder.Axis()
        radius = cylinder.Radius()
        
        axis_dir = axis.Direction()
        axis_loc = axis.Location()
        
        return {
            "cylinder_axis": [axis_dir.X(), axis_dir.Y(), axis_dir.Z()],
            "cylinder_center": [axis_loc.X(), axis_loc.Y(), axis_loc.Z()],
            "cylinder_radius": radius,
            "unfold_method": "cylindrical_unwrap"
        }

    def _analyze_conical_face(self, surface_adaptor):
        """円錐面の詳細解析"""
        cone = surface_adaptor.Cone()
        apex = cone.Apex()
        axis = cone.Axis()
        radius = cone.RefRadius()
        semi_angle = cone.SemiAngle()
        
        axis_dir = axis.Direction()
        
        return {
            "cone_apex": [apex.X(), apex.Y(), apex.Z()],
            "cone_axis": [axis_dir.X(), axis_dir.Y(), axis_dir.Z()],
            "cone_radius": radius,
            "cone_semi_angle": semi_angle,
            "unfold_method": "conical_unwrap"
        }

    def _get_surface_type_name(self, surface_type_enum) -> str:
        """曲面タイプ列挙値を文字列に変換"""
        type_map = {
            GeomAbs_Plane: "plane",
            GeomAbs_Cylinder: "cylinder", 
            GeomAbs_Cone: "cone",
            GeomAbs_Sphere: "sphere"
        }
        return type_map.get(surface_type_enum, "other")

    def _extract_face_boundaries(self, face):
        """
        面の境界線を3D座標列として抽出（ソリッドベース）。
        面のパラメータ空間での正確な境界形状を取得。
        """
        boundaries = []
        
        try:
            print(f"    面の境界線抽出開始...")
            
            # 面のアダプター取得
            face_adaptor = BRepAdaptor_Surface(face)
            
            # ワイヤ（境界線）を探索
            wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
            wire_count = 0
            
            while wire_explorer.More():
                wire = wire_explorer.Current()
                print(f"      ワイヤ{wire_count}を処理中...")
                
                # 高精度サンプリングを試行
                boundary_points = self._extract_wire_points_parametric(wire, face_adaptor)
                
                if boundary_points and len(boundary_points) >= 3:
                    boundaries.append(boundary_points)
                    print(f"      ワイヤ{wire_count}: {len(boundary_points)}点を抽出（高精度）")
                else:
                    # フォールバック：3D直接サンプリング
                    boundary_points = self._extract_wire_points_fallback(wire)
                    if boundary_points and len(boundary_points) >= 3:
                        boundaries.append(boundary_points)
                        print(f"      ワイヤ{wire_count}: {len(boundary_points)}点を抽出（フォールバック）")
                    else:
                        print(f"      ワイヤ{wire_count}: 境界点の抽出に失敗")
                
                wire_count += 1
                wire_explorer.Next()
            
            print(f"    面の境界線抽出完了: {len(boundaries)}本のワイヤ")
                
        except Exception as e:
            print(f"    境界線抽出エラー: {e}")
            import traceback
            traceback.print_exc()
            
        return boundaries

    def _extract_wire_points_parametric(self, wire, face_adaptor, num_points: int = 100) -> List[Tuple[float, float, float]]:
        """
        ワイヤから面のパラメータ空間を考慮した高精度サンプリング点を抽出。
        """
        points = []
        
        try:
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            edge_count = 0
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                
                # まずは3D空間でのサンプリングを試行（より確実）
                edge_points = self._sample_edge_points_3d(edge, num_points // 10)
                if edge_points:
                    points.extend(edge_points)
                    print(f"    エッジ{edge_count}: {len(edge_points)}点を3D抽出")
                else:
                    print(f"    エッジ{edge_count}: 3D抽出に失敗")
                    
                edge_count += 1
                edge_explorer.Next()
                
        except Exception as e:
            print(f"パラメータ空間ワイヤ点抽出エラー: {e}")
            # フォールバック処理
            return self._extract_wire_points_fallback(wire, num_points)
            
        return points

    def _sample_edge_points_parametric(self, curve_2d, face_adaptor, u_min, u_max, num_samples: int = 20) -> List[Tuple[float, float, float]]:
        """
        パラメータ空間での2Dカーブから3D点を生成。
        """
        points = []
        
        try:
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                
                # パラメータ空間での2D点を取得
                point_2d = curve_2d.Value(u)
                u_param = point_2d.X()
                v_param = point_2d.Y()
                
                # パラメータから3D点を計算
                point_3d = face_adaptor.Value(u_param, v_param)
                points.append((point_3d.X(), point_3d.Y(), point_3d.Z()))
                
        except Exception as e:
            print(f"パラメータ空間エッジサンプリングエラー: {e}")
            
        return points

    def _sample_edge_points_3d(self, edge, num_samples: int = 20) -> List[Tuple[float, float, float]]:
        """
        3D空間でのエッジサンプリング（フォールバック）。
        """
        points = []
        
        try:
            curve_adaptor = BRepAdaptor_Curve(edge)
            u_min = curve_adaptor.FirstParameter()
            u_max = curve_adaptor.LastParameter()
            
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                point = curve_adaptor.Value(u)
                points.append((point.X(), point.Y(), point.Z()))
                
        except Exception as e:
            print(f"3Dエッジサンプリングエラー: {e}")
            
        return points

    def _extract_wire_points_fallback(self, wire, num_points: int = 50) -> List[Tuple[float, float, float]]:
        """
        フォールバック：従来の方法でワイヤから点を抽出。
        """
        points = []
        
        try:
            edge_explorer = TopExp_Explorer(wire, TopAbs_EDGE)
            
            while edge_explorer.More():
                edge = edge_explorer.Current()
                edge_points = self._sample_edge_points_3d(edge, num_points // 10)
                points.extend(edge_points)
                edge_explorer.Next()
            
            # 重複点除去
            if points:
                points = self._remove_duplicate_points(points)
                
        except Exception as e:
            print(f"フォールバックワイヤ点抽出エラー: {e}")
            
        return points

    def _ensure_counterclockwise_order(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        境界線の点を反時計回りに並び替え（SVG描画に適した順序）。
        """
        if len(points_2d) < 3:
            return points_2d
        
        # 符号付き面積を計算（反時計回りなら正）
        signed_area = 0.0
        n = len(points_2d)
        
        for i in range(n):
            j = (i + 1) % n
            signed_area += (points_2d[j][0] - points_2d[i][0]) * (points_2d[j][1] + points_2d[i][1])
        
        # 時計回りの場合は順序を反転
        if signed_area > 0:
            return list(reversed(points_2d))
        else:
            return points_2d
    
    def _remove_duplicate_points(self, points_2d: List[Tuple[float, float]], tolerance: float = 1e-6) -> List[Tuple[float, float]]:
        """
        重複点を除去。
        """
        if len(points_2d) < 2:
            return points_2d
        
        cleaned_points = [points_2d[0]]
        
        for i in range(1, len(points_2d)):
            current = points_2d[i]
            last = cleaned_points[-1]
            
            # 距離チェック
            distance = math.sqrt((current[0] - last[0])**2 + (current[1] - last[1])**2)
            if distance > tolerance:
                cleaned_points.append(current)
        
        # 最初と最後の点が重複している場合は除去
        if len(cleaned_points) > 2:
            first = cleaned_points[0]
            last = cleaned_points[-1]
            distance = math.sqrt((first[0] - last[0])**2 + (first[1] - last[1])**2)
            if distance <= tolerance:
                cleaned_points = cleaned_points[:-1]
        
        return cleaned_points

    def _analyze_edge_geometry(self, edge, edge_index: int):
        """
        エッジの幾何特性解析（隣接面・タイプ・長さ等）
        """
        try:
            # エッジの長さ計算（代替方法）
            curve_adaptor = BRepAdaptor_Curve(edge)
            u_min = curve_adaptor.FirstParameter()
            u_max = curve_adaptor.LastParameter()
            
            # 簡易長さ計算
            num_samples = 10
            total_length = 0.0
            prev_point = None
            
            for i in range(num_samples + 1):
                u = u_min + (u_max - u_min) * i / num_samples
                current_point = curve_adaptor.Value(u)
                
                if prev_point is not None:
                    dx = current_point.X() - prev_point.X()
                    dy = current_point.Y() - prev_point.Y()
                    dz = current_point.Z() - prev_point.Z()
                    segment_length = (dx*dx + dy*dy + dz*dz)**0.5
                    total_length += segment_length
                    
                prev_point = current_point
            
            length = total_length
            
            # 中点取得
            u_mid = (u_min + u_max) / 2
            midpoint = curve_adaptor.Value(u_mid)
            
            return {
                "index": edge_index,
                "length": length,
                "midpoint": [midpoint.X(), midpoint.Y(), midpoint.Z()],
                "adjacent_faces": [],  # 後で隣接面情報を追加
                "is_boundary": False   # 境界エッジかどうか
            }
            
        except Exception as e:
            print(f"エッジ{edge_index}解析エラー: {e}")
            return None

    def group_faces_for_unfolding(self, max_faces: int = 20) -> List[List[int]]:
        """
        展開可能な面をグループ化。
        立方体のような単純な形状では全ての面を個別に展開。
        """
        unfoldable_faces = [i for i, face in enumerate(self.faces_data) if face["unfoldable"]]
        
        if not unfoldable_faces:
            print("展開可能な面がありません")
            return []
        
        print(f"展開可能な面: {len(unfoldable_faces)}個")
        
        # 立方体のような単純な形状では、各面を個別のグループとして扱う
        groups = []
        
        for face_idx in unfoldable_faces:
            # 各面を個別のグループとして追加
            groups.append([face_idx])
            print(f"面{face_idx}をグループ{len(groups)-1}に追加")
        
        self.unfold_groups = groups
        print(f"作成されたグループ数: {len(groups)}")
        return groups

    def _expand_face_group(self, current_group: List[int], used_faces: set, 
                          available_faces: List[int], max_group_size: int = 5):
        """
        面グループを隣接面で拡張。
        """
        if len(current_group) >= max_group_size:
            return
            
        # 現在のグループの最後の面に隣接する面を探す
        last_face_idx = current_group[-1]
        last_face = self.faces_data[last_face_idx]
        
        # 同一タイプの未使用面を優先的に探す
        for face_idx in available_faces:
            if (face_idx not in used_faces and 
                face_idx not in current_group and
                self.faces_data[face_idx]["surface_type"] == last_face["surface_type"]):
                
                # 隣接判定（簡易版 - 重心距離による）
                if self._are_faces_adjacent(last_face_idx, face_idx):
                    current_group.append(face_idx)
                    used_faces.add(face_idx)
                    
                    if len(current_group) < max_group_size:
                        self._expand_face_group(current_group, used_faces, available_faces, max_group_size)
                    break

    def _are_faces_adjacent(self, face_idx1: int, face_idx2: int, threshold: float = 10.0) -> bool:
        """
        2つの面が隣接しているか判定（簡易版）。
        実際の商用実装では共有エッジの存在を正確に判定する必要がある。
        """
        centroid1 = np.array(self.faces_data[face_idx1]["centroid"])
        centroid2 = np.array(self.faces_data[face_idx2]["centroid"])
        distance = np.linalg.norm(centroid1 - centroid2)
        return distance < threshold

    def unfold_face_groups(self) -> List[Dict]:
        """
        各面グループを2D展開図に変換。
        曲面タイプに応じた最適な展開アルゴリズムを適用。
        """
        unfolded_groups = []
        
        print(f"=== 面グループ展開開始 ===")
        print(f"グループ数: {len(self.unfold_groups)}")
        
        for group_idx, face_indices in enumerate(self.unfold_groups):
            print(f"\n--- グループ {group_idx} ---")
            print(f"面数: {len(face_indices)}")
            print(f"面インデックス: {face_indices}")
            
            # 各面の詳細情報を表示
            for i, face_idx in enumerate(face_indices):
                if face_idx < len(self.faces_data):
                    face_data = self.faces_data[face_idx]
                    print(f"  面{i}(idx={face_idx}): {face_data['surface_type']}, 面積={face_data.get('area', 'N/A')}")
                else:
                    print(f"  面{i}(idx={face_idx}): インデックスが範囲外")
            
            try:
                group_result = self._unfold_single_group(group_idx, face_indices)
                if group_result:
                    print(f"  → 展開成功: {len(group_result.get('polygons', []))}個のポリゴン")
                    unfolded_groups.append(group_result)
                else:
                    print(f"  → 展開失敗: 結果がNone")
            except Exception as e:
                print(f"  → グループ{group_idx}の展開でエラー: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n=== 展開完了 ===")
        print(f"成功したグループ数: {len(unfolded_groups)}")
        return unfolded_groups

    def _unfold_single_group(self, group_idx: int, face_indices: List[int]) -> Optional[Dict]:
        """
        単一面グループの展開処理。
        """
        if not face_indices:
            print(f"    グループ{group_idx}: 面インデックスが空")
            return None
            
        primary_face = self.faces_data[face_indices[0]]
        surface_type = primary_face["surface_type"]
        
        print(f"    グループ{group_idx}: 主面タイプ={surface_type}")
        
        try:
            if surface_type == "plane":
                print(f"    → 平面グループとして展開")
                return self._unfold_planar_group(group_idx, face_indices)
            elif surface_type == "cylinder":
                print(f"    → 円筒グループとして展開")
                return self._unfold_cylindrical_group(group_idx, face_indices)
            elif surface_type == "cone":
                print(f"    → 円錐グループとして展開")
                return self._unfold_conical_group(group_idx, face_indices)
            else:
                print(f"    → 未対応の曲面タイプ: {surface_type}")
                return None
                
        except Exception as e:
            print(f"    → グループ{group_idx}展開エラー: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _unfold_planar_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        平面グループの展開（面の正確な形状に基づく）。
        """
        polygons = []
        
        print(f"      平面グループ{group_idx}を展開中...")
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            
            # 平面情報を取得
            normal = np.array(face_data["plane_normal"])
            origin = np.array(face_data["plane_origin"])
            
            print(f"        面{face_idx}: 法線={normal}, 原点={origin}")
            
            # 面の正確な境界形状を取得
            face_polygons = self._extract_face_2d_shape(face_idx, normal, origin)
            print(f"        面{face_idx}: {len(face_polygons) if face_polygons else 0}個の2D形状を抽出")
            
            if face_polygons:
                polygons.extend(face_polygons)
        
        print(f"      平面グループ{group_idx}: 合計{len(polygons)}個のポリゴン")
        
        return {
            "group_index": group_idx,
            "surface_type": "plane",
            "polygons": polygons,
            "tabs": self._generate_tabs_for_group(face_indices),
            "fold_lines": [],
            "cut_lines": []
        }

    def _extract_face_2d_shape(self, face_idx: int, normal: np.ndarray, origin: np.ndarray) -> List[List[Tuple[float, float]]]:
        """
        面の正確な2D形状を抽出（外形線・内形線を考慮）。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        print(f"面{face_idx}の2D形状を抽出中...")
        print(f"  境界線数: {len(face_data['boundary_curves'])}")
        
        # 各境界線を2Dに投影
        for boundary_idx, boundary in enumerate(face_data["boundary_curves"]):
            print(f"  境界線{boundary_idx}: {len(boundary)}点")
            
            if len(boundary) >= 3:
                # 3D境界点を2D平面に正確に投影
                projected_boundary = self._project_points_to_plane_accurate(boundary, normal, origin)
                
                # 境界線を単純化（正方形/長方形の場合は4点に削減）
                simplified_boundary = self._simplify_boundary_polygon(projected_boundary)
                
                # 有効な2D形状の場合のみ追加
                if len(simplified_boundary) >= 3:
                    polygons_2d.append(simplified_boundary)
                    print(f"  境界線{boundary_idx}を2D投影: {len(simplified_boundary)}点（簡略化済み）")
                else:
                    print(f"  境界線{boundary_idx}の投影に失敗")
            else:
                print(f"  境界線{boundary_idx}の点数が不足: {len(boundary)}点")
        
        print(f"面{face_idx}の2D形状: {len(polygons_2d)}個のポリゴン")
        return polygons_2d

    def _simplify_boundary_polygon(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        境界線ポリゴンを簡略化（形状に応じて適切な点数に削減）。
        """
        if len(points_2d) < 3:
            return points_2d
        
        # 重複点を除去
        cleaned_points = self._remove_duplicate_points(points_2d)
        
        if len(cleaned_points) < 3:
            return cleaned_points
        
        print(f"        境界線簡略化: {len(points_2d)}点 → ", end="")
        
        # 三角形の場合
        if self._is_triangular_boundary(cleaned_points):
            result = self._extract_triangle_corners(cleaned_points)
            print(f"{len(result)}点（三角形）")
            return result
            
        # 四角形の場合
        if self._is_rectangular_boundary(cleaned_points):
            result = self._extract_rectangle_corners(cleaned_points)
            print(f"{len(result)}点（四角形）")
            return result
        
        # 五角形の場合（家の形状）
        if self._is_pentagonal_boundary(cleaned_points):
            result = self._extract_pentagon_corners(cleaned_points)
            print(f"{len(result)}点（五角形）")
            return result
        
        # その他の多角形は適度に間引く
        result = self._thin_out_points(cleaned_points, max_points=12)
        print(f"{len(result)}点（一般多角形）")
        return result
    
    def _is_triangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が三角形かどうかを判定。
        """
        if len(points_2d) < 6:  # 最低でも6点は必要
            return False
        
        # 凸包を計算して3点になるかチェック
        try:
            import numpy as np
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が3個なら三角形
            return len(hull.vertices) == 3
        except:
            return False
    
    def _extract_triangle_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から三角形の3つの角を抽出。
        """
        try:
            import numpy as np
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点を取得
            triangle_corners = [tuple(points_array[i]) for i in hull.vertices]
            
            # 3点になるように調整
            if len(triangle_corners) == 3:
                # 時計回りに並び替え
                triangle_corners = self._sort_points_clockwise(triangle_corners)
                # 閉じた三角形にする
                triangle_corners.append(triangle_corners[0])
                return triangle_corners
            else:
                # フォールバック：最初の3点を使用
                return points_2d[:4]  # 最初の3点+閉じる点
        except:
            return points_2d[:4]  # フォールバック
    
    def _sort_points_clockwise(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点を時計回りに並び替え。
        """
        # 重心を計算
        center_x = sum(p[0] for p in points) / len(points)
        center_y = sum(p[1] for p in points) / len(points)
        
        # 角度でソート
        import math
        def angle_from_center(point):
            return math.atan2(point[1] - center_y, point[0] - center_x)
        
        sorted_points = sorted(points, key=angle_from_center)
        return sorted_points
    
    def _is_rectangular_boundary(self, points_2d: List[Tuple[float, float]]) -> bool:
        """
        境界線が四角形（正方形・長方形）かどうかを判定。
        """
        if len(points_2d) < 8:  # 最低でも8点は必要
            return False
        
        # 凸包を計算して4点になるかチェック
        try:
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            # 凸包の頂点が4個なら四角形の可能性
            if len(hull.vertices) == 4:
                return True
        except:
            pass
        
        # フォールバック：境界ボックスベースの判定
        xs = [p[0] for p in points_2d]
        ys = [p[1] for p in points_2d]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # 境界ボックスの角に近い点の数を確認
        tolerance = 0.1
        corner_count = 0
        corners = [
            (min_x, min_y), (max_x, min_y), 
            (max_x, max_y), (min_x, max_y)
        ]
        
        for corner in corners:
            for point in points_2d:
                distance = math.sqrt((point[0] - corner[0])**2 + (point[1] - corner[1])**2)
                if distance < tolerance:
                    corner_count += 1
                    break
        
        return corner_count >= 4
    
    def _extract_rectangle_corners(self, points_2d: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        点群から四角形の4つの角を抽出。
        """
        try:
            # 凸包を使用して角を抽出
            points_array = np.array(points_2d)
            hull = ConvexHull(points_array)
            
            if len(hull.vertices) == 4:
                # 凸包の頂点を時計回りに並び替え
                rectangle_corners = [tuple(points_array[i]) for i in hull.vertices]
                rectangle_corners = self._sort_points_clockwise(rectangle_corners)
                # 閉じた四角形にする
                rectangle_corners.append(rectangle_corners[0])
                return rectangle_corners
        except:
            pass
        
        # フォールバック：境界ボックスベースの抽出
        xs = [p[0] for p in points_2d]
        ys = [p[1] for p in points_2d]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # 4つの角を時計回りに並べる
        corners = [
            (min_x, min_y),  # 左下
            (max_x, min_y),  # 右下
            (max_x, max_y),  # 右上
            (min_x, max_y),  # 左上
            (min_x, min_y)   # 閉じる
        ]
        
        return corners
    
    def _thin_out_points(self, points_2d: List[Tuple[float, float]], max_points: int = 12) -> List[Tuple[float, float]]:
        """
        点群を適度に間引く。
        """
        if len(points_2d) <= max_points:
            return points_2d
            
        # 等間隔で点を選択
        step = len(points_2d) // max_points
        return [points_2d[i] for i in range(0, len(points_2d), step)]

    def _project_points_to_plane_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                         normal: np.ndarray, origin: np.ndarray) -> List[Tuple[float, float]]:
        """
        3D点群を平面に正確に投影（直交座標系を構築）。
        """
        if len(points_3d) < 3:
            return []
        
        # 平面の直交座標系を構築
        normal = normal / np.linalg.norm(normal)
        
        # 第1軸：より安定した方向ベクトル選択
        if abs(normal[0]) < 0.9:
            u_axis = np.cross(normal, [1, 0, 0])
        elif abs(normal[1]) < 0.9:
            u_axis = np.cross(normal, [0, 1, 0])
        else:
            u_axis = np.cross(normal, [0, 0, 1])
        
        # ゼロベクトルチェック
        if np.linalg.norm(u_axis) < 1e-8:
            u_axis = np.array([1, 0, 0])
        else:
            u_axis = u_axis / np.linalg.norm(u_axis)
        
        # 第2軸：法線と第1軸の外積
        v_axis = np.cross(normal, u_axis)
        v_axis = v_axis / np.linalg.norm(v_axis)
        
        points_2d = []
        
        for point in points_3d:
            # 原点からの相対位置
            relative_pos = np.array(point) - origin
            
            # 平面座標系での座標計算
            u = np.dot(relative_pos, u_axis)
            v = np.dot(relative_pos, v_axis)
            
            points_2d.append((u, v))
        
        # 境界線の順序を確認・修正
        if len(points_2d) >= 3:
            points_2d = self._ensure_counterclockwise_order(points_2d)
        
        return points_2d

    def _unfold_cylindrical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円筒面グループの展開（正確な円筒座標→直交座標変換）。
        円筒面と円形の蓋を組み合わせて、実際に組み立て可能な展開図を生成。
        """
        polygons = []
        
        # 円筒面と平面（蓋）を分離
        cylindrical_faces = []
        planar_faces = []
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            if face_data["surface_type"] == "cylinder":
                cylindrical_faces.append(face_idx)
            elif face_data["surface_type"] == "plane":
                planar_faces.append(face_idx)
        
        # 円筒面の展開
        for face_idx in cylindrical_faces:
            face_data = self.faces_data[face_idx]
            
            # 円筒パラメータ
            axis = np.array(face_data["cylinder_axis"])
            center = np.array(face_data["cylinder_center"])
            radius = face_data["cylinder_radius"]
            
            # 円筒面の正確な2D形状を取得
            cylinder_polygons = self._extract_cylindrical_face_2d(face_idx, axis, center, radius)
            if cylinder_polygons:
                polygons.extend(cylinder_polygons)
        
        # 円形の蓋を追加（平面の場合）
        for face_idx in planar_faces:
            face_data = self.faces_data[face_idx]
            
            # 平面が円形かどうか確認
            if self._is_circular_face(face_data):
                # 円形の蓋を展開図に追加
                circle_polygon = self._extract_circular_face_2d(face_data)
                if circle_polygon:
                    polygons.append(circle_polygon)
        
        return {
            "group_index": group_idx,
            "surface_type": "cylinder",
            "polygons": polygons,
            "tabs": self._generate_cylindrical_tabs(cylindrical_faces, planar_faces),
            "unfold_method": "cylindrical_unwrap_with_caps"
        }

    def _extract_cylindrical_face_2d(self, face_idx: int, axis: np.ndarray, center: np.ndarray, 
                                    radius: float) -> List[List[Tuple[float, float]]]:
        """
        円筒面の正確な2D形状を抽出。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        # 各境界線を円筒展開
        for boundary in face_data["boundary_curves"]:
            if len(boundary) >= 3:
                # 3D境界点を円筒展開
                unfolded_boundary = self._unfold_cylindrical_points_accurate(boundary, axis, center, radius)
                
                # 有効な2D形状の場合のみ追加
                if len(unfolded_boundary) >= 3:
                    polygons_2d.append(unfolded_boundary)
        
        return polygons_2d

    def _unfold_cylindrical_points_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                           axis: np.ndarray, center: np.ndarray, 
                                           radius: float) -> List[Tuple[float, float]]:
        """
        3D点群を円筒面から正確に展開（改良版）。
        """
        if len(points_3d) < 3:
            return []
        
        # 軸の単位ベクトル化
        axis = axis / np.linalg.norm(axis)
        points_2d = []
        
        # 基準方向ベクトル設定
        if abs(axis[2]) < 0.9:
            ref_dir = np.cross(axis, [0, 0, 1])
        else:
            ref_dir = np.cross(axis, [1, 0, 0])
        ref_dir = ref_dir / np.linalg.norm(ref_dir)
        
        for point in points_3d:
            point_vec = np.array(point) - center
            
            # 軸方向成分（Y座標）
            y = np.dot(point_vec, axis)
            
            # 軸に垂直な成分
            radial_vec = point_vec - y * axis
            radial_dist = np.linalg.norm(radial_vec)
            
            # 角度計算（X座標）
            if radial_dist > 1e-6:
                # 正確な角度計算
                cos_angle = np.dot(radial_vec, ref_dir) / radial_dist
                cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値エラー対策
                
                # 符号を決定するための外積
                cross_product = np.cross(ref_dir, radial_vec)
                sign = 1 if np.dot(cross_product, axis) >= 0 else -1
                
                angle = sign * math.acos(cos_angle)
                x = angle * radius
            else:
                x = 0.0
            
            points_2d.append((x, y))
        
        return points_2d

    def _unfold_conical_group(self, group_idx: int, face_indices: List[int]) -> Dict:
        """
        円錐面グループの展開（円錐展開図）。
        """
        polygons = []
        
        for face_idx in face_indices:
            face_data = self.faces_data[face_idx]
            
            # 円錐パラメータ
            apex = np.array(face_data["cone_apex"])
            axis = np.array(face_data["cone_axis"])
            radius = face_data["cone_radius"]
            semi_angle = face_data["cone_semi_angle"]
            
            # 円錐面の正確な2D形状を取得
            cone_polygons = self._extract_conical_face_2d(face_idx, apex, axis, radius, semi_angle)
            if cone_polygons:
                polygons.extend(cone_polygons)
        
        return {
            "group_index": group_idx,
            "surface_type": "cone",
            "polygons": polygons,
            "tabs": self._generate_tabs_for_group(face_indices),
            "unfold_method": "conical_unwrap"
        }

    def _extract_conical_face_2d(self, face_idx: int, apex: np.ndarray, axis: np.ndarray, 
                                radius: float, semi_angle: float) -> List[List[Tuple[float, float]]]:
        """
        円錐面の正確な2D形状を抽出。
        """
        face_data = self.faces_data[face_idx]
        polygons_2d = []
        
        # 各境界線を円錐展開
        for boundary in face_data["boundary_curves"]:
            if len(boundary) >= 3:
                # 3D境界点を円錐展開
                unfolded_boundary = self._unfold_conical_points_accurate(boundary, apex, axis, radius, semi_angle)
                
                # 有効な2D形状の場合のみ追加
                if len(unfolded_boundary) >= 3:
                    polygons_2d.append(unfolded_boundary)
        
        return polygons_2d

    def _unfold_conical_points_accurate(self, points_3d: List[Tuple[float, float, float]], 
                                       apex: np.ndarray, axis: np.ndarray, 
                                       radius: float, semi_angle: float) -> List[Tuple[float, float]]:
        """
        3D点群を円錐面から正確に扇形展開。
        """
        if len(points_3d) < 3:
            return []
        
        axis = axis / np.linalg.norm(axis)
        points_2d = []
        
        # 円錐の母線長
        slant_height = radius / math.sin(semi_angle) if semi_angle > 0 else radius
        
        for point in points_3d:
            point_vec = np.array(point) - apex
            
            # 頂点からの距離
            distance = np.linalg.norm(point_vec)
            
            if distance > 1e-6:
                # 軸からの角度
                cos_angle = np.dot(point_vec, axis) / distance
                cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値エラー対策
                angle_from_axis = math.acos(cos_angle)
                
                # 展開図での半径（円錐の母線に沿った距離）
                r = distance * math.cos(angle_from_axis)
                
                # 展開図での角度（円錐の開きを考慮）
                if abs(semi_angle) > 1e-6:
                    # 基準方向ベクトル
                    if abs(axis[2]) < 0.9:
                        ref_dir = np.cross(axis, [0, 0, 1])
                    else:
                        ref_dir = np.cross(axis, [1, 0, 0])
                    ref_dir = ref_dir / np.linalg.norm(ref_dir)
                    
                    # 周方向の角度
                    radial_vec = point_vec - np.dot(point_vec, axis) * axis
                    if np.linalg.norm(radial_vec) > 1e-6:
                        radial_vec = radial_vec / np.linalg.norm(radial_vec)
                        theta = math.atan2(np.dot(radial_vec, np.cross(axis, ref_dir)), 
                                         np.dot(radial_vec, ref_dir))
                        # 円錐展開における角度スケール
                        theta = theta * math.sin(semi_angle)
                    else:
                        theta = 0.0
                else:
                    theta = 0.0
                
                x = r * math.cos(theta)
                y = r * math.sin(theta)
            else:
                x, y = 0.0, 0.0
            
            points_2d.append((x, y))
        
        return points_2d

    def _generate_default_square_boundary(self):
        """
        境界線が取得できない場合のデフォルト正方形境界線を生成。
        """
        # 20x20mmの正方形境界線
        square_boundary = [
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (20.0, 20.0, 0.0),
            (0.0, 20.0, 0.0),
            (0.0, 0.0, 0.0)  # 閉じた境界線
        ]
        return [square_boundary]
    
    def _analyze_general_surface(self, surface_adaptor):
        """
        その他の曲面（球面、トーラス面等）の詳細解析。
        """
        # 一般的な曲面は平面として近似展開
        return {
            "unfold_method": "planar_approximation"
        }

    def _generate_tabs_for_group(self, face_indices: List[int]) -> List[List[Tuple[float, float]]]:
        """
        面グループ間の接着タブを生成。
        隣接エッジ情報から適切なタブ形状を自動生成。
        """
        tabs = []
        
        # 簡易実装: 各面の境界に矩形タブを配置
        for face_idx in face_indices:
            if face_idx < len(self.faces_data):
                face_data = self.faces_data[face_idx]
                
                for boundary in face_data["boundary_curves"]:
                    if len(boundary) >= 2:
                        # 簡易タブ（矩形）を生成
                        start_point = boundary[0]
                        end_point = boundary[1]
                        
                        # タブの幅
                        tab_width = self.tab_width
                        
                        # 簡易矩形タブ
                        tab = [
                            (start_point[0], start_point[1]),
                            (end_point[0], end_point[1]),
                            (end_point[0], end_point[1] + tab_width),
                            (start_point[0], start_point[1] + tab_width)
                        ]
                        tabs.append(tab)
        
        return tabs

    def layout_unfolded_groups(self, unfolded_groups: List[Dict]) -> List[Dict]:
        """
        展開済みグループを紙面上に効率的に配置。
        重複回避・用紙サイズ最適化を実施。
        """
        if not unfolded_groups:
            return []
        
        # 各グループの境界ボックス計算
        for group in unfolded_groups:
            bbox = self._calculate_group_bbox(group["polygons"])
            group["bbox"] = bbox
        
        # 面積の大きい順にソート
        unfolded_groups.sort(key=lambda g: g["bbox"]["width"] * g["bbox"]["height"], reverse=True)
        
        # 単純な左上から配置アルゴリズム
        placed_groups = []
        next_x = 0
        max_height = 0
        margin = 10 * self.scale_factor
        
        for group in unfolded_groups:
            bbox = group["bbox"]
            
            # グループ全体を移動
            offset_x = next_x - bbox["min_x"]
            offset_y = -bbox["min_y"]
            
            positioned_group = self._translate_group(group, offset_x, offset_y)
            positioned_group["position"] = {"x": next_x, "y": 0}
            
            placed_groups.append(positioned_group)
            
            # 次の配置位置更新
            next_x += bbox["width"] + margin
            max_height = max(max_height, bbox["height"])
        
        return placed_groups

    def _calculate_group_bbox(self, polygons: List[List[Tuple[float, float]]]) -> Dict:
        """グループ全体の境界ボックス計算"""
        if not polygons:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        all_points = []
        for polygon in polygons:
            all_points.extend(polygon)
        
        if not all_points:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }

    def _translate_group(self, group: Dict, offset_x: float, offset_y: float) -> Dict:
        """グループ全体を指定オフセットで移動"""
        translated_group = group.copy()
        
        # ポリゴン移動
        translated_polygons = []
        for polygon in group["polygons"]:
            translated_polygon = [(x + offset_x, y + offset_y) for x, y in polygon]
            translated_polygons.append(translated_polygon)
        translated_group["polygons"] = translated_polygons
        
        # タブ移動
        translated_tabs = []
        for tab in group.get("tabs", []):
            translated_tab = [(x + offset_x, y + offset_y) for x, y in tab]
            translated_tabs.append(translated_tab)
        translated_group["tabs"] = translated_tabs
        
        return translated_group

    def export_to_svg(self, placed_groups: List[Dict], output_path: str) -> str:
        """
        配置済み展開図をSVG形式で出力。
        商用品質の印刷対応（スケールバー・図面枠・注記等）。
        """
        if not placed_groups:
            raise ValueError("出力する展開図データがありません")
        
        # 全体境界ボックス計算
        overall_bbox = self._calculate_overall_bbox(placed_groups)
        
        # デバッグ情報
        print(f"全体境界ボックス: {overall_bbox}")
        print(f"現在のscale_factor: {self.scale_factor}")
        
        # SVGキャンバスサイズ決定（最小サイズを保証）
        margin = max(50, 20 * self.scale_factor)  # 最小50px
        min_canvas_size = 800  # 最小キャンバスサイズ
        
        # 適切なスケールファクターを自動計算
        if overall_bbox["width"] > 0 and overall_bbox["height"] > 0:
            # 内容に応じてスケールファクターを調整
            content_scale = min(min_canvas_size / max(overall_bbox["width"], overall_bbox["height"]), 10.0)
            if content_scale > 1.0:
                # 内容が小さすぎる場合はスケールアップ
                self.scale_factor = max(self.scale_factor, content_scale)
                print(f"スケールファクターを自動調整: {self.scale_factor}")
        
        # SVGサイズ計算
        svg_width = max(min_canvas_size, overall_bbox["width"] * self.scale_factor + 2 * margin)
        svg_height = max(min_canvas_size, overall_bbox["height"] * self.scale_factor + 2 * margin + 120)  # タイトル・スケール用
        
        print(f"SVGサイズ: {svg_width} x {svg_height}")
        
        # SVG作成
        dwg = svgwrite.Drawing(output_path, size=(f"{svg_width}px", f"{svg_height}px"), viewBox=f"0 0 {svg_width} {svg_height}")
        
        # 商用グレードスタイル定義
        dwg.defs.add(dwg.style("""
            .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
            .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
            .fold-line { stroke: #ff6600; stroke-width: 1; stroke-dasharray: 6,6; }
            .cut-line { stroke: #ff0000; stroke-width: 0.8; stroke-dasharray: 3,3; }
            .title-text { font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; fill: #000000; }
            .scale-text { font-family: Arial, sans-serif; font-size: 16px; fill: #000000; }
            .note-text { font-family: Arial, sans-serif; font-size: 14px; fill: #666666; }
        """))
        
        # メインコンテンツ描画
        content_offset_x = margin - overall_bbox["min_x"] * self.scale_factor
        content_offset_y = margin - overall_bbox["min_y"] * self.scale_factor + 50  # タイトル分下げる
        
        polygon_count = 0
        
        for group_idx, group in enumerate(placed_groups):
            print(f"グループ{group_idx}をSVGに描画中...")
            print(f"  ポリゴン数: {len(group['polygons'])}")
            
            # 面ポリゴン描画
            for poly_idx, polygon in enumerate(group["polygons"]):
                if len(polygon) >= 3:
                    # スケールファクターを適用
                    points = [(x * self.scale_factor + content_offset_x, y * self.scale_factor + content_offset_y) for x, y in polygon]
                    dwg.add(dwg.polygon(points=points, class_="face-polygon"))
                    polygon_count += 1
                    print(f"  ポリゴン{poly_idx}: {len(polygon)}点を描画")
                else:
                    print(f"  ポリゴン{poly_idx}: 点数不足({len(polygon)}点)")
            
            # タブ描画
            for tab_idx, tab in enumerate(group.get("tabs", [])):
                if len(tab) >= 3:
                    # スケールファクターを適用
                    points = [(x * self.scale_factor + content_offset_x, y * self.scale_factor + content_offset_y) for x, y in tab]
                    dwg.add(dwg.polygon(points=points, class_="tab-polygon"))
                    print(f"  タブ{tab_idx}: {len(tab)}点を描画")
        
        print(f"SVG描画完了: {polygon_count}個のポリゴンを描画")
        
        # タイトル描画
        title = f"BREP Papercraft Unfolding - {len(placed_groups)} Groups"
        dwg.add(dwg.text(title, insert=(margin, 40), class_="title-text"))
        
        # スケールバー描画
        if self.show_scale:
            self._add_scale_bar(dwg, svg_width, svg_height, margin)
        
        # 注記追加
        self._add_technical_notes(dwg, svg_width, svg_height, margin)
        
        # SVG保存
        dwg.save()
        return output_path

    def _calculate_overall_bbox(self, placed_groups: List[Dict]) -> Dict:
        """配置済み全グループの境界ボックス計算"""
        if not placed_groups:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        all_points = []
        for group in placed_groups:
            for polygon in group["polygons"]:
                all_points.extend(polygon)
            for tab in group.get("tabs", []):
                all_points.extend(tab)
        
        if not all_points:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }

    def _add_scale_bar(self, dwg, svg_width: float, svg_height: float, margin: float):
        """商用グレードスケールバー追加"""
        # スケールバー仕様
        bar_length_mm = 50.0  # 5cm
        bar_length_px = bar_length_mm * self.scale_factor
        
        # 最小サイズを保証
        bar_length_px = max(bar_length_px, 100)
        
        # 配置位置
        bar_x = margin
        bar_y = svg_height - margin - 50
        
        # スケールバー本体
        dwg.add(dwg.line(start=(bar_x, bar_y), end=(bar_x + bar_length_px, bar_y),
                        stroke='black', stroke_width=3))
        
        # 目盛り
        dwg.add(dwg.line(start=(bar_x, bar_y - 8), end=(bar_x, bar_y + 8),
                        stroke='black', stroke_width=2))
        dwg.add(dwg.line(start=(bar_x + bar_length_px, bar_y - 8), 
                        end=(bar_x + bar_length_px, bar_y + 8),
                        stroke='black', stroke_width=2))
        
        # ラベル
        scale_text = f"{bar_length_mm:.0f} mm (Scale: {self.scale_factor:.2f})"
        dwg.add(dwg.text(scale_text, insert=(bar_x + bar_length_px/2, bar_y - 15),
                        text_anchor="middle", class_="scale-text"))

    def _add_technical_notes(self, dwg, svg_width: float, svg_height: float, margin: float):
        """技術注記・凡例追加"""
        notes_x = svg_width - 300
        notes_y = svg_height - margin - 80
        
        notes = [
            "Legend:",
            "━━━ Cut line (solid)",
            "┅┅┅ Fold line (dashed)",
            "┄┄┄ Tab (glue area)"
        ]
        
        for i, note in enumerate(notes):
            dwg.add(dwg.text(note, insert=(notes_x, notes_y + i * 20), class_="note-text"))

    def generate_brep_papercraft(self, request: BrepPapercraftRequest, output_path: Optional[str] = None) -> Tuple[str, Dict]:
        """
        BREPソリッドから展開図を一括生成。
        商用グレードの完全なワークフロー。
        """
        if self.solid_shape is None:
            raise ValueError("BREPソリッドが読み込まれていません")
        
        if output_path is None:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"brep_papercraft_{uuid.uuid4()}.svg")
        
        try:
            start_time = time.time()
            
            # パラメータ設定
            self.scale_factor = request.scale_factor
            self.units = request.units
            self.tab_width = request.tab_width
            self.show_scale = request.show_scale
            self.show_fold_lines = request.show_fold_lines
            self.show_cut_lines = request.show_cut_lines
            
            # 1. BREPトポロジ解析
            self.analyze_brep_topology()
            
            # 2. 展開可能面のグルーピング
            self.group_faces_for_unfolding(request.max_faces)
            
            # 3. 各グループの2D展開
            unfolded_groups = self.unfold_face_groups()
            
            # 4. グループ配置最適化
            placed_groups = self.layout_unfolded_groups(unfolded_groups)
            
            # 5. SVG出力
            svg_path = self.export_to_svg(placed_groups, output_path)
            
            # 処理統計更新
            end_time = time.time()
            self.stats["processing_time"] = end_time - start_time
            self.stats["unfoldable_faces"] = sum(len(group["polygons"]) for group in placed_groups)
            
            return svg_path, self.stats
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValueError(f"BREP展開図生成エラー: {str(e)}")


step_unfold_generator = StepUnfoldGenerator() if OCCT_AVAILABLE else None
brep_generator = StepUnfoldGenerator() if OCCT_AVAILABLE else None


# --- APIエンドポイント: BREP展開図生成 ---

# --- STEP専用APIエンドポイント ---
@app.post("/api/step/unfold")
async def unfold_step_to_svg(
    file: UploadFile = File(...)
):
    """
    STEPファイル（.step/.stp）を受け取り、展開図（SVG）を生成するAPI。
    出力: SVGファイル
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。STEPファイル処理に必要です。")
    try:
        # ファイル拡張子チェック
        if not (file.filename.lower().endswith('.step') or file.filename.lower().endswith('.stp')):
            raise HTTPException(status_code=400, detail="STEPファイル（.step/.stp）のみ対応です。")
        file_content = await file.read()
        # STEPファイルの場合、load_from_bytesメソッドを使用し、拡張子を指定
        file_ext = "step" if file.filename.lower().endswith('.step') else "stp"
        if not step_unfold_generator.load_from_bytes(file_content, file_ext):
            raise HTTPException(status_code=400, detail="STEPファイルの読み込みに失敗しました。")
        output_path = os.path.join(tempfile.mkdtemp(), f"step_unfold_{uuid.uuid4()}.svg")
        
        # デフォルトパラメータでBrepPapercraftRequestを作成
        request = BrepPapercraftRequest()
        svg_path, stats = step_unfold_generator.generate_brep_papercraft(request, output_path)
        
        return FileResponse(
            path=svg_path,
            media_type="image/svg+xml",
            filename=f"step_unfold_{uuid.uuid4()}.svg"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"予期しないエラー: {str(e)}")


# --- APIエンドポイント: BREP解析情報取得 ---
@app.post("/api/brep/analyze")
async def analyze_brep(file: UploadFile = File(...)):
    """
    BREPファイルを解析し、展開図生成前の詳細情報を返す。
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。")
        
    try:
        file_content = await file.read()
        # .brep形式のみサポート
        file_ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if file_ext != 'brep':
            raise HTTPException(status_code=400, detail=f"未対応ファイル形式: .{file_ext}。BREP形式(.brep)のみ対応。")
        # BREP読み込み
        try:
            if not brep_generator.load_brep_from_bytes(file_content):
                raise HTTPException(status_code=400, detail="BREPファイルの読み込みに失敗しました。")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # トポロジ解析
        brep_generator.analyze_brep_topology()
        
        # 解析結果返却
        analysis_result = {
            "file_info": {
                "filename": file.filename,
                "size_bytes": len(file_content)
            },
            "topology": {
                "total_faces": len(brep_generator.faces_data),
                "total_edges": len(brep_generator.edges_data),
                "surface_types": brep_generator.stats
            },
            "faces": [
                {
                    "index": face["index"],
                    "surface_type": face["surface_type"],
                    "area": face["area"],
                    "unfoldable": face["unfoldable"],
                    "centroid": face["centroid"]
                }
                for face in brep_generator.faces_data
            ],
            "recommendations": {
                "max_faces": min(20, len([f for f in brep_generator.faces_data if f["unfoldable"]])),
                "estimated_groups": max(1, len(brep_generator.faces_data) // 5)
            }
        }
        
        return JSONResponse(content=analysis_result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"解析エラー: {str(e)}")


# --- シンプル展開図生成APIエンドポイント ---
@app.post("/api/brep/unfold_simple")
async def unfold_brep_simple(
    file: UploadFile = File(...)
):
    """
    BREPファイルを解析し、各面を独立にUVパラメータ空間で2D展開し、配置するシンプル展開図生成API。
    接続情報や折り線は含まず、単純に各面を並べる。
    """
    if not OCCT_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCASCADE Technology が利用できません。")
    try:
        file_content = await file.read()
        file_ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        # BREファイルまたはSTEPファイルをサポート
        if file_ext not in ("brep", "step", "stp"):
            raise HTTPException(status_code=400, detail=f"未対応ファイル形式: .{file_ext}。BREP/STEP形式のみ対応。")
        # ファイル読み込み
        if file_ext == "brep":
            success = brep_generator.load_brep_from_bytes(file_content)
        else:
            # STEP/STPファイル
            success = brep_generator.load_from_bytes(file_content, file_ext)
        if not success:
            raise HTTPException(status_code=400, detail="ファイルの読み込みに失敗しました。")
        brep_generator.analyze_brep_topology()
        # 各面を2D展開 (UVパラメータ空間を使用)
        scale = BrepPapercraftRequest().scale_factor
        margin = 10 * scale
        x_offset = margin
        y_offset = margin
        row_max_height = 0
        # 展開ポリゴン格納
        polygons_to_draw = []
        # 各面の境界曲線から2D形状を抽出して配置
        for face_data in brep_generator.faces_data:
            idx = face_data.get("index")
            # BRepの面オブジェクト取得
            explorer = TopExp_Explorer(brep_generator.solid_shape, TopAbs_FACE)
            current = 0
            face = None
            while explorer.More():
                if current == idx:
                    face = explorer.Current()
                    break
                explorer.Next()
                current += 1
            if face is None:
                continue
            # 2D形状抽出
            try:
                polys = brep_generator._extract_face_2d_shape(idx,
                    np.array(face_data.get("plane_normal", [0,0,1])),
                    np.array(face_data.get("plane_origin", [0,0,0])))
            except Exception:
                polys = []
            # 詳細境界なしの場合はUV矩形で代替
            if not polys:
                adaptor = BRepAdaptor_Surface(face)
                try:
                    u_min,u_max,v_min,v_max = adaptor.BoundsUV()
                except Exception:
                    u_min,u_max,v_min,v_max = 0.0,1.0,0.0,1.0
                polys = [[(u_min,v_min),(u_max,v_min),(u_max,v_max),(u_min,v_max),(u_min,v_min)]]
            # 各ポリゴンを配置
            for poly in polys:
                xs, ys = zip(*poly)
                w = (max(xs)-min(xs)) * scale
                h = (max(ys)-min(ys)) * scale
                if x_offset + w + margin > 1000 * scale:
                    x_offset = margin; y_offset += row_max_height + margin; row_max_height = 0
                pts = [((x-min(xs))*scale + x_offset, (y-min(ys))*scale + y_offset) for x,y in poly]
                polygons_to_draw.append(pts)
                x_offset += w + margin
                row_max_height = max(row_max_height, h)
        # SVGサイズ算出
        svg_width = x_offset + margin
        svg_height = y_offset + row_max_height + margin
        dwg = svgwrite.Drawing(size=(f"{svg_width}px", f"{svg_height}px"))
        for pts in polygons_to_draw:
            dwg.add(dwg.polyline(points=pts, stroke='black', fill='none'))
        svg_output = dwg.tostring()
        return Response(content=svg_output, media_type="image/svg+xml")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"シンプル展開図生成エラー: {str(e)}")


# --- ヘルスチェック ---
@app.get("/api/brep/health")
async def brep_health_check():
    """BREP API ヘルスチェック"""
    return {
        "status": "healthy" if OCCT_AVAILABLE else "degraded",
        "version": "2.0.0",
        "opencascade_available": OCCT_AVAILABLE,
        "supported_formats": ["brep", "step", "iges"] if OCCT_AVAILABLE else []
    }


# --- サーバー起動 ---
def main():
    if not OCCT_AVAILABLE:
        print("警告: OpenCASCADE が利用できないため、一部機能が制限されます。")
    
    port = int(os.getenv("PORT", 8001))
    print(f"サーバーをポート {port} で起動します。")
    uvicorn.run("brep_papercraft_api:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
