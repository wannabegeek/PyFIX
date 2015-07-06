import datetime
import unittest
from pyfix.event import EventManager, TimerEventRegistration


class EventTimerTests(unittest.TestCase):
    def testTimerEvent(self):
        mgr = EventManager()
        endTime = None
        t1 = TimerEventRegistration(lambda fire, closure: self.assertEqual(int((datetime.datetime.utcnow() - closure).total_seconds()), 1), 1.0, datetime.datetime.utcnow())
        mgr.registerHandler(t1)
        mgr.waitForEventWithTimeout(5.0)

    def testTimerEventReset(self):
        mgr = EventManager()
        t1 = TimerEventRegistration(lambda fire, closure: self.assertEqual(int((datetime.datetime.utcnow() - closure).total_seconds()), 2), 1.0, datetime.datetime.utcnow())
        mgr.registerHandler(t1)
        mgr.registerHandler(TimerEventRegistration(lambda fire, closure: t1.reset(), 0.9))

        for i in range(0, 3):
            mgr.waitForEventWithTimeout(10.0)
