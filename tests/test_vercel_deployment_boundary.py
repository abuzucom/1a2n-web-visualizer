"""Hold the Vercel deployment boundary in place."""
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / '.github/workflows'
DEPLOY_PAGES_ACTION = 'actions/deploy-pages@'


def workflow_paths() -> list:
    """Return every workflow file in the repository."""
    return sorted(WORKFLOW_DIR.glob('*.yml')) + sorted(WORKFLOW_DIR.glob('*.yaml'))


class VercelDeploymentBoundaryTest(unittest.TestCase):
    """Check the actual Vercel deployment configuration."""

    def test_vercel_config_publishes_site_tree(self) -> None:
        """Vercel config publishes the site tree."""
        config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
        self.assertIsNone(config['framework'])
        self.assertEqual(config['outputDirectory'], 'src')
        self.assertEqual(config['installCommand'], '')
        self.assertEqual(config['buildCommand'], '')

    def test_upload_keeps_only_site_tree(self) -> None:
        """Upload keeps only the site tree."""
        lines = (ROOT / '.vercelignore').read_text(encoding='utf-8').splitlines()
        patterns = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
        self.assertIn('*', patterns)
        self.assertIn('!src/', patterns)
        self.assertIn('!src/**', patterns)

    def test_no_workflow_publishes_github_pages(self) -> None:
        self.assertFalse((WORKFLOW_DIR / 'deploy.yml').exists())
        for path in workflow_paths():
            workflow = yaml.safe_load(path.read_text(encoding='utf-8'))
            for job in (workflow.get('jobs') or {}).values():
                for step in job.get('steps') or []:
                    uses = step.get('uses', '')
                    self.assertFalse(uses.startswith(DEPLOY_PAGES_ACTION), path.name)


if __name__ == '__main__':
    unittest.main()
