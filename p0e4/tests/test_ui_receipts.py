import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integration.ui_receipts import validate
from integration.contracts import digest


class UIReceiptTests(unittest.TestCase):
    def setUp(self):
        self.r = dict(schema='P0E4_UI_EXECUTION_RECEIPT', schema_version=1,
            request_id='TEST_ONLY', surface='TEST_ONLY_UI', status='COMPLETED',
            request_sha256=digest(b'request'), result_sha256=digest(b'result'),
            submitted_at='2026-09-18T22:00:00Z', observed_at='2026-09-18T22:01:00Z',
            NON_PUBLISHING=True, production_deployment_authorized=False,
            publication_authorized=False, first_real_poster='PAUSED_BY_NITIN',
            provider_signed=False, durable_dispatcher_proven=False, real_media_qc_proven=False,
            observation_source='computer_use_ui', historical_task_reused=False,
            observed_events=['submission_observed', 'completion_observed'], result_capture='rendered_text')

    def test_observation_never_grants_execution_or_retry(self):
        self.assertEqual(validate(self.r,b'request',b'result'),
            dict(receipt_valid=True,production_eligible=False,publication_eligible=False,retry_safe=False))

    def test_tamper_historical_approval_and_false_completion_rejected(self):
        for key,value in [('request_sha256','0'*64),('result_sha256','0'*64),
            ('historical_task_reused',True),('publication_authorized',True),
            ('production_deployment_authorized',True),('provider_signed',True),
            ('durable_dispatcher_proven',True),('real_media_qc_proven',True),
            ('NON_PUBLISHING',False),('observed_events',['submission_observed']),
            ('submitted_at','2026-09-18T23:00:00Z')]:
            with self.subTest(key=key):
                r=copy.deepcopy(self.r);r[key]=value
                with self.assertRaises(ValueError):validate(r,b'request',b'result')

    def test_pending_requires_no_invented_output(self):
        self.r.update(status='RUNNING',result_sha256=None,observed_events=['submission_observed'])
        self.assertTrue(validate(self.r,b'request')['receipt_valid'])
        self.r['status']='COMPLETED'
        with self.assertRaises(ValueError):validate(self.r,b'request')


if __name__ == '__main__': unittest.main()
