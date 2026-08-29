from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from .models import CutRange, WordCaption


PROJECT_VERSION = 1


@dataclass
class ProjectState:
    source: Path
    captions: list[WordCaption]
    cuts: list[CutRange]
    position_ms: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "version": PROJECT_VERSION,
            "source": str(self.source),
            "captions": [asdict(caption) for caption in self.captions],
            "cuts": [asdict(cut) for cut in self.cuts],
            "position_ms": max(0, int(self.position_ms)),
            "updated_at": self.updated_at or datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ProjectState":
        if payload.get("version") != PROJECT_VERSION:
            raise ValueError("Este projeto foi criado por uma versão incompatível do Glimo Editor.")
        source = Path(str(payload.get("source", "")))
        if not str(source):
            raise ValueError("O projeto não informa o vídeo de origem.")
        try:
            captions = [WordCaption(**item) for item in payload.get("captions", [])]
            cuts = [CutRange(**item) for item in payload.get("cuts", [])]
        except (TypeError, ValueError) as exc:
            raise ValueError("O projeto contém cortes ou legendas inválidos.") from exc
        return cls(
            source=source,
            captions=captions,
            cuts=cuts,
            position_ms=max(0, int(payload.get("position_ms", 0))),
            updated_at=str(payload.get("updated_at", "")),
        )


def save_project(path: Path, state: ProjectState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_project(path: Path) -> ProjectState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Não foi possível ler este projeto do Glimo Editor.") from exc
    if not isinstance(payload, dict):
        raise ValueError("O arquivo de projeto não é válido.")
    return ProjectState.from_dict(payload)


class SessionStore:
    """Mantém instantâneos recuperáveis sem alterar os vídeos de origem."""

    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.root = base / "sessions"
        self.index_path = self.root / "recent.json"

    def _read_index(self) -> list[dict]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write_index(self, entries: list[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries[:30], ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.index_path)

    def snapshot_path(self, source: Path) -> Path:
        key = hashlib.sha256(str(source.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
        return self.root / f"{key}.glimo"

    def save(self, state: ProjectState) -> Path:
        snapshot = self.snapshot_path(state.source)
        save_project(snapshot, state)
        entries = [entry for entry in self._read_index() if entry.get("project") != str(snapshot)]
        entries.insert(
            0,
            {
                "project": str(snapshot),
                "source": str(state.source),
                "name": state.source.name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._write_index(entries)
        return snapshot

    def recent(self) -> list[dict]:
        return [entry for entry in self._read_index() if Path(str(entry.get("project", ""))).is_file()]

    def remove(self, project_path: Path) -> None:
        entries = [entry for entry in self._read_index() if entry.get("project") != str(project_path)]
        self._write_index(entries)
        project_path.unlink(missing_ok=True)

