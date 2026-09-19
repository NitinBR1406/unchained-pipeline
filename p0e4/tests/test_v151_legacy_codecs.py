import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical.legacy_codecs import *
class Codecs(unittest.TestCase):
 def test_tokens_zero_drift(self):
  for k,v in [('hashtags',['#AakhriIshq','#UNCHAINED']),('keywords',['vocal performance','Hindi'])]:
   self.assertEqual(decode_tokens(encode_tokens(v,k),k),v)
 def test_lossy_tokens_fail(self):
  for k,v in [('hashtags',['#a #b']),('keywords',['a,b']),('keywords',[' a']),('hashtags',['a']),('keywords',[])]:
   with self.assertRaises(ValueError):encode_tokens(v,k)
 def test_wire_not_silently_normalized(self):
  for k,v in [('hashtags','#a  #b'),('keywords','a,  b'),('hashtags','#a\n#b')]:
   with self.assertRaises(ValueError):decode_tokens(v,k)
 def test_schedule_instant_zero_drift(self):
  for canonical,wire in [('2026-09-19T18:00:00Z','2026-09-19 20:00:00'),('2026-01-19T18:00:00Z','2026-01-19 19:00:00')]:
   self.assertEqual(encode_schedule(canonical),wire);self.assertEqual(decode_schedule(wire),canonical)
 def test_dst_and_precision_fail_closed(self):
  for wall in ['2026-10-25 02:30:00','2026-03-29 02:30:00']:
   with self.assertRaises(ValueError):decode_schedule(wall)
  for val in ['2026-09-19T18:00:00','2026-09-19T18:00:00.123Z','2026-10-25T00:30:00Z']:
   with self.assertRaises(ValueError):encode_schedule(val)
if __name__=='__main__':unittest.main()
