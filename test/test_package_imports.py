import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


class PackageImportTests(unittest.TestCase):
    def test_can_import_caption_models_without_flet_dependency(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, r"{repo_root}")
            from interface.flet_player.domain.caption_models import CaptionSegment
            segment = CaptionSegment(id=1, start=0.0, end=1.0, text="ok", language="en")
            print(segment.text)
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertEqual("ok", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
