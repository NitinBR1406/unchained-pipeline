import json, unittest
from pathlib import Path
from p0e4.resolve.caption_kit import CaptionKitError, build_cache_key, validate_render_gate
ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/"p0e4/resolve/templates/UNCHAINED_CAPTION_KIT_V01/config.json"
class CaptionKitTests(unittest.TestCase):
 def setUp(self): self.cfg=json.loads(CFG.read_text())
 def test_font_gate_fails_closed(self):
  with self.assertRaisesRegex(CaptionKitError,"Montserrat,Cinzel"): validate_render_gate(self.cfg)
 def test_cache_changes_with_second_text(self):
  a=next(v for v in self.cfg["variants"] if v["id"]=="EMOTIONAL_OPENING"); b=self.cfg["second_text_reuse_proof"]["variant"]
  source=json.loads((ROOT/"p0e4/evidence/native_caption_rhythm_parallel_v01_execution/agent1_caption/SOURCE_BINDING.json").read_text())
  self.assertNotEqual(build_cache_key(a,a["template_sha256"],self.cfg["render_contract"],source),build_cache_key(b,b["template_sha256"],self.cfg["render_contract"],source))
 def test_actual_lyrics_remain_hold(self): self.assertEqual("HOLD",self.cfg["variants"][-1]["actual_lyric_mode"])
