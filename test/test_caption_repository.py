import importlib.util
import pickle
import sys
import tempfile
import types
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_ROOT = _ROOT / "interface" / "flet_player"


def _ensure_package(package_name: str, package_path: Path) -> None:
    if package_name in sys.modules:
        return
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package


def _load_module(module_name: str, relative_path: str):
    module_path = _ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package("interface", _ROOT / "interface")
_ensure_package("interface.flet_player", _PACKAGE_ROOT)
_ensure_package("interface.flet_player.domain", _PACKAGE_ROOT / "domain")
_ensure_package("interface.flet_player.infrastructure", _PACKAGE_ROOT / "infrastructure")
caption_models = _load_module("interface.flet_player.domain.caption_models", "interface/flet_player/domain/caption_models.py")
_load_module("interface.flet_player.infrastructure.caption_pickle_io", "interface/flet_player/infrastructure/caption_pickle_io.py")
caption_repository = _load_module(
    "interface.flet_player.infrastructure.caption_repository",
    "interface/flet_player/infrastructure/caption_repository.py",
)
CaptionSegment = caption_models.CaptionSegment
CaptionRepository = caption_repository.CaptionRepository


class CaptionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = CaptionRepository()

    def test_load_sorts_segments_and_builds_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.caption"
            raw_segments = [
                {"id": 2, "start": 5.0, "end": 7.0, "text": "later", "language": "en"},
                {"id": 1, "start": 1.0, "end": 2.0, "text": "earlier", "language": "en"},
            ]
            with open(path, "wb") as file_obj:
                pickle.dump(raw_segments, file_obj)

            loaded = self.repository.load(path)

        self.assertEqual(["earlier", "later"], [segment.text for segment in loaded])
        self.assertTrue(all(isinstance(segment, CaptionSegment) for segment in loaded))

    def test_save_round_trips_caption_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.caption"
            segments = [
                CaptionSegment(id=1, start=0.0, end=1.2, text="hello", language="en"),
                CaptionSegment(id=2, start=1.3, end=2.8, text="world", language="en"),
            ]

            self.repository.save(segments, path)

            with open(path, "rb") as file_obj:
                raw_segments = pickle.load(file_obj)

        self.assertEqual("hello", raw_segments[0]["text"])
        self.assertEqual(2.8, raw_segments[1]["end"])


if __name__ == "__main__":
    unittest.main()
