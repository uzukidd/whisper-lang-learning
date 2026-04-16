import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_root_main():
    module_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("project_root_main", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class MainEntryTests(unittest.TestCase):
    def test_run_uses_flet_app_runner(self) -> None:
        module = _load_root_main()
        fake_ft = types.SimpleNamespace(AppView=types.SimpleNamespace(FLET_APP="FLET_APP"))
        fake_page = object()
        called: dict[str, object] = {}

        def fake_build_video_player_page(page, initial_video_uri=None):
            called["page"] = page
            called["initial"] = initial_video_uri

        def fake_runner(entrypoint, view=None):
            called["view"] = view
            entrypoint(fake_page)

        module.run(
            argv=["main.py", "sample.mp4"],
            app_runner=fake_runner,
            flet_module=fake_ft,
            page_builder=fake_build_video_player_page,
        )

        self.assertEqual("FLET_APP", called["view"])
        self.assertIs(fake_page, called["page"])
        self.assertEqual("sample.mp4", called["initial"])


if __name__ == "__main__":
    unittest.main()
