"""CAD Import + Geometry stage runner (stages 01+02).

Delegates to existing Level 1-3 interoperability adapters.
GEOMETRY is extracted in the same pass as CAD_IMPORT — both stages complete together.
"""
from __future__ import annotations

import os
from pathlib import Path

from ..enums import StageStatus, WorkflowStage
from ..models import EvidenceLabel, KnownUnknown, StageResult, WorkflowContext
from .base import StageRunner


class CadImportRunner(StageRunner):
    stage = WorkflowStage.CAD_IMPORT

    def run(self, ctx: WorkflowContext) -> StageResult:  # noqa: PLR0911
        file_ref = ctx.source_file_ref
        if not file_ref:
            return self._blocked(
                "No source file provided — cannot run CAD import",
                ctx,
                known_unknowns=[
                    KnownUnknown(
                        category="source_file",
                        description="Source CAD file reference is missing",
                        stage=WorkflowStage.CAD_IMPORT,
                    )
                ],
            )

        result = StageResult(
            stage=self.stage,
            status=StageStatus.RUNNING,
            input_refs={"source_file": file_ref, "workflow_id": ctx.workflow_id},
        )

        file_path = str(file_ref)
        # Resolve artifact ref → absolute path (Level-20 durable storage)
        if not os.path.exists(file_path):
            try:
                from backend.api.cad_upload import resolve_file_ref
                file_path = resolve_file_ref(file_path)
            except (ValueError, Exception):
                pass
        if not os.path.exists(file_path):
            result.status = StageStatus.BLOCKED
            result.blocking_reasons.append(f"File not found: {file_ref}")
            result.known_unknowns.append(
                KnownUnknown(
                    category="file_not_found",
                    description=f"CAD file does not exist at path: {file_ref}",
                    stage=WorkflowStage.CAD_IMPORT,
                )
            )
            result.finish()
            return result

        ext = os.path.splitext(file_path)[1].lower()
        try:
            geo_ref = self._parse_file(file_path, ext, ctx, result)
        except Exception as exc:
            result.status = StageStatus.FAILED
            result.errors.append(f"CAD parse error: {exc!r}")
            result.finish()
            return result

        if geo_ref is None:
            result.status = StageStatus.PARTIAL
            result.warnings.append(f"Unsupported or empty geometry for extension: {ext}")
        else:
            ctx.geometry_ref = geo_ref
            result.output_refs["geometry_ref"] = geo_ref
            result.provenance["cad_format"] = ext
            result.provenance["evidence"] = EvidenceLabel.CONFIRMED
            result.status = StageStatus.PASS

        result.finish()
        return result

    def _parse_file(
        self, file_path: str, ext: str, ctx: WorkflowContext, result: StageResult
    ) -> str | None:
        """Route to the appropriate interoperability adapter and return a geometry ref."""
        if ext == ".dxf":
            return self._parse_dxf(file_path, ctx, result)
        if ext in (".igs", ".iges"):
            return self._parse_iges(file_path, ctx, result)
        if ext in (".stp", ".step"):
            return self._parse_step(file_path, ctx, result)
        return None

    def _parse_dxf(self, path: str, ctx: WorkflowContext, result: StageResult) -> str | None:
        from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
        from backend.interoperability.enums import NormalizationStatus
        from backend.interoperability.models import EngineeringSource

        source = EngineeringSource(
            source_id=f"WF_{ctx.workflow_id}_DXF",
            source_format_id=DXF_DESCRIPTOR.format_id,
            file_name=os.path.basename(path),
        )
        adapter = DxfTokenAdapter()
        doc = adapter.ingest_file(source, DXF_DESCRIPTOR, Path(path))
        _failed = {NormalizationStatus.FAILED, NormalizationStatus.INSUFFICIENT_DATA}
        if doc.normalization_status in _failed:
            result.warnings.append(f"DXF parse did not succeed: {doc.normalization_status}")
            return None
        geo_ref = f"GEO_DXF_{ctx.workflow_id}"
        ctx.cad_provenance = {"format": "DXF", "path": path, "ref": geo_ref}
        result.provenance["adapter"] = "DxfTokenAdapter"
        result.provenance["normalization_status"] = str(doc.normalization_status)
        return geo_ref

    def _parse_iges(self, path: str, ctx: WorkflowContext, result: StageResult) -> str | None:
        from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
        from backend.interoperability.enums import NormalizationStatus
        from backend.interoperability.models import EngineeringSource

        source = EngineeringSource(
            source_id=f"WF_{ctx.workflow_id}_IGES",
            source_format_id=IGES_DESCRIPTOR.format_id,
            file_name=os.path.basename(path),
        )
        adapter = IgesTokenAdapter()
        doc = adapter.ingest_file(source, IGES_DESCRIPTOR, Path(path))
        _failed = {NormalizationStatus.FAILED, NormalizationStatus.INSUFFICIENT_DATA}
        if doc.normalization_status in _failed:
            result.warnings.append(f"IGES parse did not succeed: {doc.normalization_status}")
            return None
        geo_ref = f"GEO_IGES_{ctx.workflow_id}"
        ctx.cad_provenance = {"format": "IGES", "path": path, "ref": geo_ref}
        result.provenance["adapter"] = "IgesTokenAdapter"
        result.provenance["normalization_status"] = str(doc.normalization_status)
        return geo_ref

    def _parse_step(self, path: str, ctx: WorkflowContext, result: StageResult) -> str | None:
        from backend.interoperability.adapters.step import STEP_GENERIC, StepTokenAdapter
        from backend.interoperability.enums import NormalizationStatus
        from backend.interoperability.models import EngineeringSource

        source = EngineeringSource(
            source_id=f"WF_{ctx.workflow_id}_STEP",
            source_format_id=STEP_GENERIC.format_id,
            file_name=os.path.basename(path),
        )
        adapter = StepTokenAdapter()
        doc = adapter.ingest_file(source, STEP_GENERIC, Path(path))
        _failed = {NormalizationStatus.FAILED, NormalizationStatus.INSUFFICIENT_DATA}
        if doc.normalization_status in _failed:
            result.warnings.append(f"STEP parse did not succeed: {doc.normalization_status}")
            return None
        geo_ref = f"GEO_STEP_{ctx.workflow_id}"
        ctx.cad_provenance = {"format": "STEP", "path": path, "ref": geo_ref}
        result.provenance["adapter"] = "StepTokenAdapter"
        result.provenance["normalization_status"] = str(doc.normalization_status)
        return geo_ref
