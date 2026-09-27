import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import write_manifest as manifest

class ManifestTests(unittest.TestCase):
    def test_clean_locked_install_without_playwright(self):
        def version(name):
            if name=='playwright':raise manifest.importlib.metadata.PackageNotFoundError(name)
            return 'synthetic-version'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();home=Path(folder)/'codex'
            with patch.object(manifest,'ROOT',root),patch.object(manifest,'codex_home',lambda:home),patch.object(manifest,'resolve_key',lambda:(None,'missing')),patch.object(manifest,'statistics',lambda:{}),patch.object(manifest.importlib.metadata,'version',version):
                path=manifest.write_manifest()
                data=json.loads(path.read_text('utf-8'))
            self.assertNotIn('playwright',data['runtime']['versions'])
            self.assertEqual(data['credential']['configured'],False)
            self.assertEqual(data['tests']['direct_jev_api'],'NOT_RUN')
            self.assertEqual(data['runtime']['codex_version'],'not_probed')

if __name__=='__main__':unittest.main()
