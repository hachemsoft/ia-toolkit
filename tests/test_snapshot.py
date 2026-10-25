import json, os, unittest
import snapshot

class InstallSnapshotTests(unittest.TestCase):
 """Safety net for refactors: what the installer writes does not change unless the reference is rewritten on purpose."""
 @unittest.skipIf(os.name=='nt','reference recorded with POSIX paths')
 def test_install_matches_golden(self):
  reference=json.loads(snapshot.GOLDEN.read_text(encoding='utf-8'))
  changes=snapshot.diff(reference,snapshot.capture_all())
  self.assertEqual(changes,[],'installation differs from the reference; if intended: python3 tests/snapshot.py --update')
if __name__=='__main__':unittest.main()
