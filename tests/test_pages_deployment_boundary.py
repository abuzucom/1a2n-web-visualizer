"""Preserve Pages deployment permissions and retry behavior."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class PagesDeploymentBoundaryTest(unittest.TestCase):
    """Check the actual Pages deployment configuration."""

    def test_pages_retry_and_permissions_remain(self) -> None:
        workflow = yaml.safe_load((ROOT / '.github/workflows/deploy.yml').read_text(encoding='utf-8'))
        self.assertEqual(workflow['permissions'], {
            'contents': 'read', 'pages': 'write', 'id-token': 'write',
        })
        job = workflow['jobs']['deploy']
        self.assertEqual(job['environment']['name'], 'github-pages')
        steps = {step['id']: step for step in job['steps'] if 'id' in step}
        self.assertTrue(steps['deployment']['continue-on-error'])
        self.assertEqual(steps['retry']['if'], "steps.deployment.outcome == 'failure'")
        self.assertNotIn('continue-on-error', steps['retry'])
        self.assertEqual(steps['deployment']['uses'], steps['retry']['uses'])
        self.assertTrue(steps['deployment']['uses'].startswith('actions/deploy-pages@'))


if __name__ == '__main__':
    unittest.main()
