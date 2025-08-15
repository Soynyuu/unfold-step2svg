import os
import tempfile
import uuid
from typing import List, Dict, Optional
import svgwrite


class SVGExporter:
    """
    SVG出力を専門とする独立したクラス。
    展開図のSVG形式での出力機能を提供。
    """
    
    def __init__(self, scale_factor: float = 10.0, units: str = "mm", 
                 tab_width: float = 5.0, show_scale: bool = True,
                 show_fold_lines: bool = True, show_cut_lines: bool = True,
                 page_format: str = "A4"):
        """
        SVGExporterを初期化。
        
        Args:
            scale_factor: スケール倍率
            units: 単位系
            tab_width: タブ幅
            show_scale: スケールバーを表示するか
            show_fold_lines: 折り線を表示するか
            show_cut_lines: 切断線を表示するか
            page_format: ページフォーマット (A4, A3, Letter)
        """
        self.scale_factor = scale_factor
        self.units = units
        self.tab_width = tab_width
        self.show_scale = show_scale
        self.show_fold_lines = show_fold_lines
        self.show_cut_lines = show_cut_lines
        self.page_format = page_format
        
        # A4サイズの定義 (210x297mm -> px at 96 DPI)
        self.page_sizes = {
            "A4": {"width": 794, "height": 1123, "width_mm": 210, "height_mm": 297},
            "A3": {"width": 1123, "height": 1587, "width_mm": 297, "height_mm": 420},
            "Letter": {"width": 816, "height": 1056, "width_mm": 216, "height_mm": 279}
        }
        
        # 印刷マージン (mm -> px)
        self.print_margin_mm = 10  # 10mm margin
        self.print_margin_px = self.print_margin_mm * 3.78  # 96 DPI conversion
    
    def export_to_svg(self, placed_groups: List[Dict], output_path: str,
                     layout_manager=None) -> str:
        """
        配置済み展開図をSVG形式で出力。
        商用品質の印刷対応（スケールバー・図面枠・注記等）。
        
        Args:
            placed_groups: 配置済みのグループデータ
            output_path: 出力パス
            layout_manager: レイアウトマネージャー（境界ボックス計算用）
        
        Returns:
            str: 出力されたSVGファイルのパス
        """
        if not placed_groups:
            raise ValueError("出力する展開図データがありません")
        
        # 全体境界ボックス計算
        if layout_manager:
            overall_bbox = layout_manager.calculate_overall_bbox(placed_groups)
        else:
            overall_bbox = self._calculate_overall_bbox(placed_groups)
        
        # ページサイズ取得
        page_size = self.page_sizes[self.page_format]
        
        print(f"ページフォーマット: {self.page_format}")
        print(f"全体境界ボックス: {overall_bbox}")
        
        # 適切なスケール計算（線が読めるサイズ確保）
        if overall_bbox["width"] > 0 and overall_bbox["height"] > 0:
            # 最小/最大スケールの範囲で調整
            min_scale = 3.0  # 線が見える最小サイズ
            max_scale = 15.0  # 過度に大きくならない
            
            # 内容サイズに応じた適切なスケール
            if max(overall_bbox["width"], overall_bbox["height"]) < 50:
                # 小さい図形は大きく
                optimal_scale = max_scale
            elif max(overall_bbox["width"], overall_bbox["height"]) > 200:
                # 大きい図形は適度に
                optimal_scale = min_scale
            else:
                # 中程度の図形は中間スケール
                optimal_scale = (min_scale + max_scale) / 2
            
            self.scale_factor = optimal_scale
            print(f"最適スケール: {self.scale_factor:.2f}")
        
        # SVGサイズを内容に合わせて動的調整
        scaled_content_width = overall_bbox["width"] * self.scale_factor
        scaled_content_height = overall_bbox["height"] * self.scale_factor
        
        # 十分な余白を確保
        margin = 50
        svg_width = scaled_content_width + 2 * margin
        svg_height = scaled_content_height + 2 * margin + 100  # タイトル・スケール用
        
        # 最小サイズを保証
        svg_width = max(svg_width, 600)
        svg_height = max(svg_height, 400)
        
        print(f"動的SVGサイズ: {svg_width:.1f} x {svg_height:.1f} px")
        
        # SVG作成 (内容に合わせたサイズ)
        dwg = svgwrite.Drawing(
            output_path, 
            size=(f"{svg_width}px", f"{svg_height}px"), 
            viewBox=f"0 0 {svg_width} {svg_height}"
        )
        
        # 商用グレードスタイル定義
        dwg.defs.add(dwg.style("""
            .face-polygon { fill: none; stroke: #000000; stroke-width: 2; }
            .tab-polygon { fill: none; stroke: #0066cc; stroke-width: 1.5; stroke-dasharray: 4,4; }
            .fold-line { stroke: #ff6600; stroke-width: 1; stroke-dasharray: 6,6; }
            .cut-line { stroke: #ff0000; stroke-width: 0.8; stroke-dasharray: 3,3; }
            .title-text { font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; fill: #000000; }
            .scale-text { font-family: Arial, sans-serif; font-size: 16px; fill: #000000; }
            .note-text { font-family: Arial, sans-serif; font-size: 14px; fill: #666666; }
            .face-number { font-family: Arial, sans-serif; font-size: 140px; font-weight: bold; fill: #ff0000; text-anchor: middle; }
        """))
        
        # メインコンテンツを適切にオフセット
        content_offset_x = margin - overall_bbox["min_x"] * self.scale_factor
        content_offset_y = margin + 60 - overall_bbox["min_y"] * self.scale_factor  # タイトル分下げる
        
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
                    
                    # 面番号を描画（ポリゴンの中心に配置）
                    print(f"  グループデータ: face_numbers={group.get('face_numbers', 'なし')}")
                    if "face_numbers" in group and poly_idx < len(group["face_numbers"]):
                        # ポリゴンの中心を計算
                        center_x = sum(p[0] for p in points) / len(points)
                        center_y = sum(p[1] for p in points) / len(points)
                        
                        # 面のサイズに基づいてフォントサイズを計算
                        font_size = self._calculate_face_number_size(points)
                        
                        # 面番号テキストを追加（動的サイズで）
                        face_number = group["face_numbers"][poly_idx]
                        dwg.add(dwg.text(
                            str(face_number),
                            insert=(center_x, center_y),
                            style=f"font-family: Arial, sans-serif; font-size: {font_size}px; font-weight: bold; fill: #ff0000; text-anchor: middle;",
                            dominant_baseline="middle"  # 垂直中央揃え
                        ))
                        print(f"    面番号{face_number}を中心({center_x:.1f}, {center_y:.1f})にサイズ{font_size:.1f}pxで描画")
                    else:
                        print(f"    面番号なし: poly_idx={poly_idx}, face_numbers存在={('face_numbers' in group)}")
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
        
        # タイトル描画 (ページ上部中央)
        title = f"Diorama-CAD(mitou-jr) - {len(placed_groups)} Groups"
        title_x = svg_width / 2
        title_y = 40
        dwg.add(dwg.text(title, insert=(title_x, title_y), text_anchor="middle", class_="title-text"))
        
        # スケールバー描画
        
        # 注記追加
        self._add_technical_notes(dwg, svg_width, svg_height)
        
        # SVG保存
        dwg.save()
        return output_path
    
    def _add_scale_bar(self, dwg, svg_width: float, svg_height: float):
        """動的サイズ用スケールバー追加"""
        # スケールバー仕様
        bar_length_mm = 50.0  # 50mm (5cm)
        bar_length_px = bar_length_mm * self.scale_factor / 10  # スケールに合わせて調整
        
        # 配置位置 (左下)
        bar_x = 50
        bar_y = svg_height - 50
        
        # スケールバー本体
        dwg.add(dwg.line(start=(bar_x, bar_y), end=(bar_x + bar_length_px, bar_y),
                        stroke='black', stroke_width=2))
        
        # 目盛り
        dwg.add(dwg.line(start=(bar_x, bar_y - 6), end=(bar_x, bar_y + 6),
                        stroke='black', stroke_width=1.5))
        dwg.add(dwg.line(start=(bar_x + bar_length_px, bar_y - 6), 
                        end=(bar_x + bar_length_px, bar_y + 6),
                        stroke='black', stroke_width=1.5))
        
        # ラベル
        scale_text = f"{bar_length_mm:.0f} mm"
        dwg.add(dwg.text(scale_text, insert=(bar_x + bar_length_px/2, bar_y - 12),
                        text_anchor="middle", class_="scale-text"))

    def _calculate_polygon_area(self, points):
        """
        ポリゴンの面積を計算（Shoelace formula）
        
        Args:
            points: ポリゴンの頂点リスト [(x, y), ...]
            
        Returns:
            面積（絶対値）
        """
        n = len(points)
        if n < 3:
            return 0
        
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        
        return abs(area) / 2
    
    def _calculate_face_number_size(self, polygon_points):
        """
        面の大きさに基づいて適切なフォントサイズを計算
        
        Args:
            polygon_points: ポリゴンの頂点リスト（SVG座標系）
            
        Returns:
            適切なフォントサイズ（px）
        """
        if len(polygon_points) < 3:
            return 40  # デフォルトサイズ
        
        # 境界ボックスを計算
        xs = [p[0] for p in polygon_points]
        ys = [p[1] for p in polygon_points]
        
        bbox_width = max(xs) - min(xs)
        bbox_height = max(ys) - min(ys)
        
        # 最小辺長を取得
        min_dimension = min(bbox_width, bbox_height)
        
        # フォントサイズを面の最小辺の35%に設定
        # （番号が面内に収まりやすいサイズ）
        font_size = min_dimension * 0.35
        
        # 最小・最大サイズでクリップ
        # 最小: 20px（読める最小サイズ）
        # 最大: 200px（大きすぎない上限）
        font_size = max(20, min(200, font_size))
        
        return font_size
    
    def _add_technical_notes(self, dwg, svg_width: float, svg_height: float):
        """動的サイズ用技術注記・凡例追加"""
        notes_x = svg_width - 250
        notes_y = svg_height - 80
        
        notes = [
            "切り取り線 (Cut Lines)",
            "━━━ 実線で切断",
        ]
        
        for i, note in enumerate(notes):
            dwg.add(dwg.text(note, insert=(notes_x, notes_y + i * 18), class_="note-text"))
    
    def _calculate_overall_bbox(self, placed_groups: List[Dict]) -> Dict:
        """
        全体境界ボックスを計算（layout_managerがない場合のフォールバック）
        """
        if not placed_groups:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for group in placed_groups:
            for polygon in group.get("polygons", []):
                for x, y in polygon:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
            
            for tab in group.get("tabs", []):
                for x, y in tab:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        
        return {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }
    
    def update_settings(self, scale_factor: Optional[float] = None, 
                       units: Optional[str] = None, 
                       tab_width: Optional[float] = None,
                       show_scale: Optional[bool] = None,
                       show_fold_lines: Optional[bool] = None,
                       show_cut_lines: Optional[bool] = None):
        """
        設定を更新する
        """
        if scale_factor is not None:
            self.scale_factor = scale_factor
        if units is not None:
            self.units = units
        if tab_width is not None:
            self.tab_width = tab_width
        if show_scale is not None:
            self.show_scale = show_scale
        if show_fold_lines is not None:
            self.show_fold_lines = show_fold_lines
        if show_cut_lines is not None:
            self.show_cut_lines = show_cut_lines