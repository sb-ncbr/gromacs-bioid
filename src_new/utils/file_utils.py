import json
import math
import os
import tempfile
from pathlib import Path

try:
    import numpy as _np
except ImportError:  # pragma: no cover - numpy is present in workers
    _np = None


def _sanitize_for_json(obj):
    """Recursively prepare data for JSON serialization.

    Replaces NaN/Inf with None and converts numpy scalars/arrays to their
    Python-native equivalents (np.float32 & friends are not JSON
    serializable and isinstance(np.float32(...), float) is False).
    """
    if _np is not None and isinstance(obj, _np.generic):
        return _sanitize_for_json(obj.item())
    if _np is not None and isinstance(obj, _np.ndarray):
        return _sanitize_for_json(obj.tolist())
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {key: _sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    else:
        return obj


def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON data atomically using a temp file and os.replace.
    
    Creates parent directories if missing.
    Writes JSON with indent=4 to a temp file in the same directory.
    Cleans up temp file on failure.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create temp file in the same directory
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_sanitize_for_json(data), f, indent=4, allow_nan=False)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
