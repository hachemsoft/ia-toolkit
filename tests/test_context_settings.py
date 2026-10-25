import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from installer.cli import apply
from installer.core import KitError
from installer.adapters.gemini import merge_context_filenames
class ContextSettingsTests(unittest.TestCase):
 def test_absent(self):
  self.assertEqual(merge_context_filenames({}),{'context':{'fileName':['30_USER.md','GEMINI.md','AGENTS.md']}})
 def test_managed_first(self):
  value={'context':{'fileName':['AGENTS.md','MINE.md']}}
  merge_context_filenames(value,['00_KIT.md','10_COMPANY.md'])
  self.assertEqual(value['context']['fileName'],['00_KIT.md','10_COMPANY.md','30_USER.md','GEMINI.md','AGENTS.md','MINE.md'])
 def test_existing_string(self):
  value={'context':{'fileName':'AGENTS.md','discoveryMaxDirs':100},'ui':{'theme':'custom'}}
  merge_context_filenames(value)
  self.assertEqual(value['context']['fileName'],['30_USER.md','GEMINI.md','AGENTS.md'])
  self.assertEqual(value['context']['discoveryMaxDirs'],100)
  self.assertEqual(value['ui'],{'theme':'custom'})
 def test_list_union_order(self):
  value={'context':{'fileName':['00_SOUL.md','AGENTS.md','GEMINI.md','AGENTS.md','65_TOOLS.md']}}
  merge_context_filenames(value)
  self.assertEqual(value['context']['fileName'],['30_USER.md','GEMINI.md','AGENTS.md','00_SOUL.md','65_TOOLS.md'])
 def test_empty_list(self):
  value={'context':{'fileName':[]}};merge_context_filenames(value)
  self.assertEqual(value['context']['fileName'],['30_USER.md','GEMINI.md','AGENTS.md'])
 def test_idempotent(self):
  value={'context':{'fileName':'GEMINI.md'}};merge_context_filenames(value);before=json.dumps(value)
  merge_context_filenames(value);self.assertEqual(before,json.dumps(value))
 def test_invalid_shapes(self):
  for context in [None,[],False,'x',{'fileName':None},{'fileName':3},{'fileName':['AGENTS.md',False]},{'fileName':''}]:
   with self.subTest(context=context), self.assertRaises(KitError):merge_context_filenames({'context':context})
 def test_invalid_setting_blocks_all_writes(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);settings=home/'.gemini/settings.json';settings.parent.mkdir()
   original=b'{"context":{"fileName":42},"ui":{"theme":"mine"}}';settings.write_bytes(original)
   with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KitError):apply('data-developer',home)
   self.assertEqual(settings.read_bytes(),original);self.assertFalse((home/'.ai-kit').exists())
