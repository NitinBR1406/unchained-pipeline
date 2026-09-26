import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; EV=ROOT/"p0e4/evidence/native_caption_rhythm_parallel_v01_execution/agent2_rhythm"
class RhythmProposalTests(unittest.TestCase):
 def test_both_are_unselected_no_render(self):
  for name,count in [("CONTROLLED_GROOVE_V02.json",12),("STRONGER_PERFORMANCE_ENERGY_V02.json",16)]:
   d=json.loads((EV/name).read_text()); self.assertEqual(count,len(d["events"])); self.assertFalse(d["global_rules"]["default_enabled"]); self.assertIn("NO_RENDER",d["status"])
 def test_instrument_and_bar_phase_not_claimed(self):
  d=json.loads((EV/"SOURCE_BINDING_VALIDATION_V01.json").read_text()); self.assertIn("NOT_PROVEN_KICK",d["analysis_semantics"]["kick_band"]); self.assertIn("NOT_PROVEN_BAR_ONE",d["analysis_semantics"]["downbeats_every_nth"]); self.assertFalse(d["resolve_used"]); self.assertFalse(d["render_performed"]);
 def test_climax_claim_rejected(self):
  d=json.loads((EV/"UNCERTAINTY_AUDIT_V01.json").read_text()); self.assertIn("92.775s is a musical or vocal climax",d["not_confirmed"])
