import importlib.util
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
_ensure_package("interface.flet_player.application", _PACKAGE_ROOT / "application")
caption_models = _load_module("interface.flet_player.domain.caption_models", "interface/flet_player/domain/caption_models.py")
asr_module = _load_module("interface.flet_player.application.asr", "interface/flet_player/application/asr.py")

CaptionSegment = caption_models.CaptionSegment
AsrService = asr_module.AsrService
AsrProvider = asr_module.AsrProvider


class FakeAsrProvider(AsrProvider):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def transcribe(self, media_path: str | Path, model_name: str = "base", device: str | None = None) -> tuple[list[CaptionSegment], str]:
        self.calls.append((str(media_path), model_name, device))
        return (
            [CaptionSegment(id=1, start=0.0, end=1.0, text="hello", language="en")],
            str(Path(media_path).with_suffix(".caption")),
        )


class AsrServiceTests(unittest.TestCase):
    def test_delegates_to_provider(self) -> None:
        provider = FakeAsrProvider()
        service = AsrService(provider)

        with tempfile.TemporaryDirectory() as temp_dir:
            media_path = Path(temp_dir) / "sample.mp4"
            media_path.write_text("demo", encoding="utf-8")

            segments, caption_path = service.transcribe(media_path, model_name="small", device="cpu")

        self.assertEqual([(str(media_path), "small", "cpu")], provider.calls)
        self.assertEqual("hello", segments[0].text)
        self.assertTrue(caption_path.endswith(".caption"))


if __name__ == "__main__":
    unittest.main()
