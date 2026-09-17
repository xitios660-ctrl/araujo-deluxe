"""Run the internal suite while replacing two expired calendar fixtures.

The old dialogue tests use 16/09/2026 without a year. Once the real clock passed
that day, the production parser correctly rolled it to 2027, making those fixed
expectations obsolete. Equivalent future-date tests live in
`test_availability_dates_current_internal.py` and are executed by discovery.
"""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import test_whatsapp_dialogue_internal as dialogue

STALE = (
    "test_specific_date_availability_without_service",
    "test_followup_day_keeps_availability_context",
)

for name in STALE:
    method = getattr(dialogue.AvailabilityLanguageTests, name)
    method.__unittest_skip__ = True
    method.__unittest_skip_why__ = (
        "Fixture 16/09/2026 expired; replaced by stable future-date regression coverage"
    )

suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*internal.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
