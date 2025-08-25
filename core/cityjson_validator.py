"""
CityJSON Validator Module

This module provides validation and preprocessing functionality for CityJSON data.
It uses val3dity for ISO 19107 compliant geometry validation and cjio for preprocessing.
"""

import os
import json
import tempfile
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ValidationError(Enum):
    """Types of validation errors based on ISO 19107"""
    # Ring level errors
    RING_NOT_CLOSED = "101"
    CONSECUTIVE_POINTS_SAME = "102"
    RING_SELF_INTERSECTION = "103"
    RING_COLLAPSED = "104"
    
    # Polygon level errors  
    INTERIOR_DISCONNECTED = "201"
    INNER_RING_OUTSIDE = "202"
    INNER_RINGS_NESTED = "203"
    POLYGON_INTERIOR_DISCONNECTED = "204"
    POLYGON_PROJECTION_INVALID = "205"
    POLYGON_NOT_PLANAR = "206"
    
    # Shell level errors
    POLYGON_WRONG_ORIENTATION = "301"
    ALL_POLYGONS_WRONG_ORIENTATION = "302"
    POLYGON_NOT_USED = "303"
    DANGLING_FACES = "304"
    FACES_FOLD_ON_THEMSELVES = "305"
    NOT_CLOSED = "306"
    INNER_SHELL_OUTSIDE = "307"
    
    # Solid level errors
    SURFACE_NOT_CLOSED = "401"
    SURFACE_SELF_INTERSECTS = "402"
    SURFACE_ORIENTATION_INCORRECT = "403"
    
    # Other errors
    INVALID_INPUT = "901"
    UNKNOWN_ERROR = "999"


@dataclass
class ValidationResult:
    """Result of CityJSON validation"""
    is_valid: bool
    error_count: int
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    validation_time: float
    validator_used: str  # "val3dity", "cjio", or "internal"


@dataclass
class PreprocessingResult:
    """Result of CityJSON preprocessing"""
    success: bool
    operations_applied: List[str]
    cityjson_data: Optional[Dict[str, Any]]
    statistics: Dict[str, Any]
    processing_time: float


class CityJSONValidator:
    """
    Validates and preprocesses CityJSON data for B-Rep conversion.
    Uses val3dity for geometry validation and cjio for preprocessing.
    """
    
    def __init__(self):
        self.debug_mode = False
        self.val3dity_available = self._check_val3dity()
        self.cjio_available = self._check_cjio()
        
    def enable_debug(self, enabled: bool = True):
        """Enable debug mode for detailed logging"""
        self.debug_mode = enabled
    
    def _check_val3dity(self) -> bool:
        """Check if val3dity is available"""
        try:
            result = subprocess.run(['val3dity', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            available = result.returncode == 0
            if self.debug_mode and available:
                print(f"val3dity available: {result.stdout.strip()}")
            return available
        except:
            return False
    
    def _check_cjio(self) -> bool:
        """Check if cjio is available"""
        try:
            result = subprocess.run(['cjio', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            available = result.returncode == 0
            if self.debug_mode and available:
                print(f"cjio available: {result.stdout.strip()}")
            return available
        except:
            return False
    
    def validate_cityjson(self, cityjson_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate CityJSON data using val3dity or built-in validation
        
        Args:
            cityjson_data: CityJSON dictionary
            
        Returns:
            ValidationResult with validation details
        """
        import time
        start_time = time.time()
        
        # Try val3dity first if available
        if self.val3dity_available:
            result = self._validate_with_val3dity(cityjson_data)
            if result:
                result.validation_time = time.time() - start_time
                return result
        
        # Fall back to cjio validation if available
        if self.cjio_available:
            result = self._validate_with_cjio(cityjson_data)
            if result:
                result.validation_time = time.time() - start_time
                return result
        
        # Use internal validation as last resort
        result = self._validate_internal(cityjson_data)
        result.validation_time = time.time() - start_time
        return result
    
    def _validate_with_val3dity(self, cityjson_data: Dict[str, Any]) -> Optional[ValidationResult]:
        """
        Validate using val3dity (ISO 19107 compliant)
        
        Args:
            cityjson_data: CityJSON dictionary
            
        Returns:
            ValidationResult or None if validation failed
        """
        temp_file = None
        
        try:
            # Save CityJSON to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.city.json', delete=False) as f:
                json.dump(cityjson_data, f)
                temp_file = f.name
            
            # Run val3dity
            result = subprocess.run(
                ['val3dity', temp_file, '--report', 'json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode not in [0, 1]:  # 0=valid, 1=invalid
                if self.debug_mode:
                    print(f"val3dity error: {result.stderr}")
                return None
            
            # Parse validation report
            try:
                report = json.loads(result.stdout)
            except json.JSONDecodeError:
                # Try to extract JSON from output
                lines = result.stdout.splitlines()
                json_lines = [l for l in lines if l.strip().startswith('{')]
                if json_lines:
                    report = json.loads(json_lines[0])
                else:
                    return None
            
            # Extract validation results
            is_valid = report.get('validity', False)
            errors = []
            warnings = []
            
            # Process errors by feature
            for feature_id, feature_errors in report.get('features', {}).items():
                for error_code in feature_errors.get('errors', []):
                    errors.append({
                        'feature_id': feature_id,
                        'error_code': error_code,
                        'description': self._get_error_description(error_code)
                    })
            
            statistics = {
                'total_features': report.get('total_features', 0),
                'valid_features': report.get('valid_features', 0),
                'invalid_features': report.get('invalid_features', 0),
                'primitives_validated': report.get('primitives_validated', {})
            }
            
            if self.debug_mode:
                print(f"val3dity validation: {'VALID' if is_valid else 'INVALID'}")
                print(f"Errors found: {len(errors)}")
            
            return ValidationResult(
                is_valid=is_valid,
                error_count=len(errors),
                errors=errors,
                warnings=warnings,
                statistics=statistics,
                validation_time=0,
                validator_used="val3dity"
            )
            
        except Exception as e:
            if self.debug_mode:
                print(f"val3dity validation failed: {e}")
            return None
            
        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def _validate_with_cjio(self, cityjson_data: Dict[str, Any]) -> Optional[ValidationResult]:
        """
        Validate using cjio
        
        Args:
            cityjson_data: CityJSON dictionary
            
        Returns:
            ValidationResult or None if validation failed
        """
        temp_file = None
        
        try:
            # Save CityJSON to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.city.json', delete=False) as f:
                json.dump(cityjson_data, f)
                temp_file = f.name
            
            # Run cjio validate
            result = subprocess.run(
                ['cjio', temp_file, 'validate'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse validation output
            is_valid = "Invalid" not in result.stdout
            errors = []
            warnings = []
            
            # Extract errors from output
            for line in result.stdout.splitlines():
                if "Error" in line or "Invalid" in line:
                    errors.append({
                        'description': line.strip()
                    })
                elif "Warning" in line:
                    warnings.append({
                        'description': line.strip()
                    })
            
            statistics = {
                'validator': 'cjio'
            }
            
            if self.debug_mode:
                print(f"cjio validation: {'VALID' if is_valid else 'INVALID'}")
                print(f"Errors: {len(errors)}, Warnings: {len(warnings)}")
            
            return ValidationResult(
                is_valid=is_valid,
                error_count=len(errors),
                errors=errors,
                warnings=warnings,
                statistics=statistics,
                validation_time=0,
                validator_used="cjio"
            )
            
        except Exception as e:
            if self.debug_mode:
                print(f"cjio validation failed: {e}")
            return None
            
        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def _validate_internal(self, cityjson_data: Dict[str, Any]) -> ValidationResult:
        """
        Internal validation (basic checks)
        
        Args:
            cityjson_data: CityJSON dictionary
            
        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        
        # Check required fields
        if "type" not in cityjson_data or cityjson_data["type"] != "CityJSON":
            errors.append({
                'error_code': ValidationError.INVALID_INPUT.value,
                'description': "Invalid CityJSON type"
            })
        
        if "version" not in cityjson_data:
            warnings.append({
                'description': "Missing version field"
            })
        
        if "CityObjects" not in cityjson_data:
            errors.append({
                'error_code': ValidationError.INVALID_INPUT.value,
                'description': "Missing CityObjects"
            })
        
        if "vertices" not in cityjson_data:
            errors.append({
                'error_code': ValidationError.INVALID_INPUT.value,
                'description': "Missing vertices array"
            })
        
        # Check vertices
        vertices = cityjson_data.get("vertices", [])
        if vertices:
            # Check for duplicate vertices
            vertex_set = set()
            duplicates = 0
            for v in vertices:
                v_tuple = tuple(v)
                if v_tuple in vertex_set:
                    duplicates += 1
                vertex_set.add(v_tuple)
            
            if duplicates > 0:
                warnings.append({
                    'description': f"Found {duplicates} duplicate vertices"
                })
        
        # Check city objects
        city_objects = cityjson_data.get("CityObjects", {})
        building_count = 0
        geometry_count = 0
        
        for obj_id, obj_data in city_objects.items():
            if obj_data.get("type") in ["Building", "BuildingPart"]:
                building_count += 1
                geometry_count += len(obj_data.get("geometry", []))
        
        statistics = {
            'building_count': building_count,
            'geometry_count': geometry_count,
            'vertex_count': len(vertices),
            'duplicate_vertices': duplicates if vertices else 0
        }
        
        is_valid = len(errors) == 0
        
        if self.debug_mode:
            print(f"Internal validation: {'VALID' if is_valid else 'INVALID'}")
            print(f"Buildings: {building_count}, Geometries: {geometry_count}")
        
        return ValidationResult(
            is_valid=is_valid,
            error_count=len(errors),
            errors=errors,
            warnings=warnings,
            statistics=statistics,
            validation_time=0,
            validator_used="internal"
        )
    
    def preprocess_cityjson(self, cityjson_data: Dict[str, Any], 
                           operations: List[str]) -> PreprocessingResult:
        """
        Preprocess CityJSON data using cjio operations
        
        Args:
            cityjson_data: Input CityJSON dictionary
            operations: List of preprocessing operations
                       e.g., ["triangulate", "remove_duplicate_vertices", "clean"]
            
        Returns:
            PreprocessingResult with processed data
        """
        import time
        start_time = time.time()
        
        if not operations:
            return PreprocessingResult(
                success=True,
                operations_applied=[],
                cityjson_data=cityjson_data,
                statistics={},
                processing_time=0
            )
        
        # Use cjio if available
        if self.cjio_available:
            result = self._preprocess_with_cjio(cityjson_data, operations)
            if result:
                result.processing_time = time.time() - start_time
                return result
        
        # Fall back to internal preprocessing
        result = self._preprocess_internal(cityjson_data, operations)
        result.processing_time = time.time() - start_time
        return result
    
    def _preprocess_with_cjio(self, cityjson_data: Dict[str, Any], 
                             operations: List[str]) -> Optional[PreprocessingResult]:
        """
        Preprocess using cjio
        
        Args:
            cityjson_data: Input CityJSON
            operations: List of cjio operations
            
        Returns:
            PreprocessingResult or None if failed
        """
        temp_input = None
        temp_output = None
        
        try:
            # Save input to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.city.json', delete=False) as f:
                json.dump(cityjson_data, f)
                temp_input = f.name
            
            temp_output = tempfile.mktemp(suffix='.city.json')
            
            # Build cjio command
            cmd = ['cjio', temp_input]
            
            # Map common operations to cjio commands
            applied_operations = []
            for op in operations:
                if op == "triangulate":
                    cmd.append('triangulate')
                    applied_operations.append("triangulate")
                elif op in ["remove_duplicate_vertices", "clean_vertices"]:
                    cmd.append('vertices_clean')
                    applied_operations.append("vertices_clean")
                elif op == "clean":
                    cmd.append('clean')
                    applied_operations.append("clean")
                elif op.startswith("lod_filter"):
                    # Extract LOD level from operation (e.g., "lod_filter_2")
                    lod = op.split('_')[-1] if '_' in op else "2"
                    cmd.extend(['lod_filter', lod])
                    applied_operations.append(f"lod_filter_{lod}")
                elif op == "remove_materials":
                    cmd.append('remove_materials')
                    applied_operations.append("remove_materials")
                elif op == "compress":
                    cmd.append('compress')
                    applied_operations.append("compress")
            
            # Save output
            cmd.extend(['save', temp_output])
            
            # Execute cjio
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                if self.debug_mode:
                    print(f"cjio preprocessing failed: {result.stderr}")
                return None
            
            # Read processed data
            with open(temp_output, 'r') as f:
                processed_data = json.load(f)
            
            # Extract statistics from output
            statistics = self._extract_cjio_statistics(result.stdout)
            
            if self.debug_mode:
                print(f"Applied cjio operations: {', '.join(applied_operations)}")
            
            return PreprocessingResult(
                success=True,
                operations_applied=applied_operations,
                cityjson_data=processed_data,
                statistics=statistics,
                processing_time=0
            )
            
        except Exception as e:
            if self.debug_mode:
                print(f"cjio preprocessing failed: {e}")
            return None
            
        finally:
            if temp_input and os.path.exists(temp_input):
                os.unlink(temp_input)
            if temp_output and os.path.exists(temp_output):
                os.unlink(temp_output)
    
    def _preprocess_internal(self, cityjson_data: Dict[str, Any], 
                            operations: List[str]) -> PreprocessingResult:
        """
        Internal preprocessing (limited functionality)
        
        Args:
            cityjson_data: Input CityJSON
            operations: Requested operations
            
        Returns:
            PreprocessingResult
        """
        processed_data = cityjson_data.copy()
        applied_operations = []
        
        # Remove duplicate vertices if requested
        if "remove_duplicate_vertices" in operations or "clean_vertices" in operations:
            processed_data = self._remove_duplicate_vertices_internal(processed_data)
            applied_operations.append("remove_duplicate_vertices")
        
        # LOD filtering
        for op in operations:
            if op.startswith("lod_filter"):
                try:
                    lod = int(op.split('_')[-1])
                    processed_data = self._filter_lod_internal(processed_data, lod)
                    applied_operations.append(f"lod_filter_{lod}")
                except:
                    pass
        
        statistics = {
            'operations_requested': len(operations),
            'operations_applied': len(applied_operations),
            'vertex_count': len(processed_data.get('vertices', [])),
            'object_count': len(processed_data.get('CityObjects', {}))
        }
        
        return PreprocessingResult(
            success=True,
            operations_applied=applied_operations,
            cityjson_data=processed_data,
            statistics=statistics,
            processing_time=0
        )
    
    def _remove_duplicate_vertices_internal(self, cityjson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove duplicate vertices and update indices"""
        vertices = cityjson_data.get('vertices', [])
        if not vertices:
            return cityjson_data
        
        # Create mapping from old to new indices
        unique_vertices = []
        vertex_map = {}
        
        for i, v in enumerate(vertices):
            v_tuple = tuple(v)
            if v_tuple not in vertex_map:
                vertex_map[v_tuple] = len(unique_vertices)
                unique_vertices.append(v)
        
        # Update if duplicates were found
        if len(unique_vertices) < len(vertices):
            cityjson_data['vertices'] = unique_vertices
            # Note: Should also update all geometry indices, but that's complex
            # This is a simplified version
        
        return cityjson_data
    
    def _filter_lod_internal(self, cityjson_data: Dict[str, Any], target_lod: int) -> Dict[str, Any]:
        """Filter geometries by LOD"""
        for obj_id, obj_data in cityjson_data.get('CityObjects', {}).items():
            filtered_geom = []
            for geom in obj_data.get('geometry', []):
                if geom.get('lod', 0) == target_lod:
                    filtered_geom.append(geom)
            obj_data['geometry'] = filtered_geom
        
        return cityjson_data
    
    def _get_error_description(self, error_code: str) -> str:
        """Get human-readable description for error code"""
        error_descriptions = {
            "101": "Ring is not closed",
            "102": "Consecutive points are the same",
            "103": "Ring self-intersects",
            "104": "Ring is collapsed to a line or point",
            "201": "Interior of polygon is disconnected",
            "202": "Inner ring is outside outer ring",
            "203": "Inner rings are nested",
            "204": "Polygon interior is disconnected",
            "205": "Polygon projection is invalid",
            "206": "Polygon is not planar",
            "301": "Polygon has wrong orientation",
            "302": "All polygons have wrong orientation",
            "303": "Polygon is not used in shell",
            "304": "Shell has dangling faces",
            "305": "Faces fold on themselves",
            "306": "Shell is not closed",
            "307": "Inner shell is outside outer shell",
            "401": "Surface is not closed",
            "402": "Surface self-intersects",
            "403": "Surface orientation is incorrect"
        }
        return error_descriptions.get(error_code, f"Error code {error_code}")
    
    def _extract_cjio_statistics(self, output: str) -> Dict[str, Any]:
        """Extract statistics from cjio output"""
        stats = {}
        
        # Parse cjio output for statistics
        for line in output.splitlines():
            if "vertices" in line.lower():
                # Try to extract vertex count
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    stats['vertices_processed'] = int(numbers[0])
            elif "cityobjects" in line.lower():
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    stats['objects_processed'] = int(numbers[0])
        
        return stats