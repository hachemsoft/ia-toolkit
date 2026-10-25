import json, os, unittest
import snapshot

class InstallSnapshotTests(unittest.TestCase):
 """Filet de sécurité des refactors : ce que l'installeur écrit ne change pas sans que la référence soit réécrite exprès."""
 @unittest.skipIf(os.name=='nt','référence enregistrée avec des chemins POSIX')
 def test_install_matches_golden(self):
  reference=json.loads(snapshot.GOLDEN.read_text(encoding='utf-8'))
  changes=snapshot.diff(reference,snapshot.capture_all())
  self.assertEqual(changes,[],'installation différente de la référence ; si c’est voulu : python3 tests/snapshot.py --update')
if __name__=='__main__':unittest.main()
