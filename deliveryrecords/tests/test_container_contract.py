from pathlib import Path
from unittest import TestCase


class DockerfileContractTests(TestCase):
    def test_dockerfile_does_not_override_entrypoint_default_command(self):
        dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
        self.assertNotIn(
            'CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]',
            dockerfile.read_text(),
        )
