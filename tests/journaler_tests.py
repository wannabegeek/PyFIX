import unittest
from pyfix.connection import MessageDirection
from pyfix.journaler import Journaler
from pyfix.message import FIXMessage, FIXContext
from pyfix.session import FIXSession


class JournalerTests(unittest.TestCase):
    def testAddExtractMsg(self):
        journal = Journaler()

        msg = FIXMessage("AB")
        msg.setField("45", "dgd")
        msg.setField("32", "aaaa")
        msg.setField("323", "bbbb")

        rptgrp1 = FIXContext()
        rptgrp1.setField("611", "aaa")
        rptgrp1.setField("612", "bbb")
        rptgrp1.setField("613", "ccc")

        msg.addRepeatingGroup("444", rptgrp1, 0)
        session = FIXSession(1, "S1", "T1")
        for i in range(0, 5):
            msg.setField("34", str(i))
            journal.persistMsg(msg, session, MessageDirection.OUTBOUND)

        msg = journal.recoverMsg(session, MessageDirection.OUTBOUND, 1)

    def testAddExtractMultipleMsgs(self):
        journal = Journaler()

        msg = FIXMessage("AB")
        msg.setField("45", "dgd")
        msg.setField("32", "aaaa")
        msg.setField("323", "bbbb")

        rptgrp1 = FIXContext()
        rptgrp1.setField("611", "aaa")
        rptgrp1.setField("612", "bbb")
        rptgrp1.setField("613", "ccc")

        msg.addRepeatingGroup("444", rptgrp1, 0)
        session = FIXSession(1, "S1", "T1")
        for i in range(0, 5):
            msg.setField("34", str(i))
            journal.persistMsg(msg, session, MessageDirection.OUTBOUND)

        msgs = journal.recoverMsgs(session, MessageDirection.OUTBOUND, 0, 4)
        for i in range(0, len(msgs)):
            msg.setField("34", str(i))
            self.assertEqual(msg, msgs[i])
