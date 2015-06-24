import pickle
from pyfix.message import FIXMessage, FIXContext

__author__ = 'tom'

import unittest


class FIXMessageTests(unittest.TestCase):
    def testMsgConstruction(self):
        msg = FIXMessage("AB")
        msg.setField("45", "dgd")
        msg.setField("32", "aaaa")
        msg.setField("323", "bbbb")

        rptgrp1 = FIXContext()
        rptgrp1.setField("611", "aaa")
        rptgrp1.setField("612", "bbb")
        rptgrp1.setField("613", "ccc")

        msg.addRepeatingGroup("444", rptgrp1, 0)

        rptgrp2 = FIXContext()
        rptgrp2.setField("611", "zzz")
        rptgrp2.setField("612", "yyy")
        rptgrp2.setField("613", "xxx")
        msg.addRepeatingGroup("444", rptgrp2, 1)

        self.assertEqual("45=dgd|32=aaaa|323=bbbb|444=2=>[611=aaa|612=bbb|613=ccc, 611=zzz|612=yyy|613=xxx]", str(msg))

        msg.removeRepeatingGroupByIndex("444", 1)
        self.assertEqual("45=dgd|32=aaaa|323=bbbb|444=1=>[611=aaa|612=bbb|613=ccc]", str(msg))

        msg.addRepeatingGroup("444", rptgrp2, 1)

        rptgrp3 = FIXContext()
        rptgrp3.setField("611", "ggg")
        rptgrp3.setField("612", "hhh")
        rptgrp3.setField("613", "jjj")
        rptgrp2.addRepeatingGroup("445", rptgrp3, 0)
        self.assertEqual("45=dgd|32=aaaa|323=bbbb|444=2=>[611=aaa|612=bbb|613=ccc, 611=zzz|612=yyy|613=xxx|445=1=>[611=ggg|612=hhh|613=jjj]]", str(msg))

        grp = msg.getRepeatingGroupByTag("444", "612", "yyy")
        self.assertEqual("611=zzz|612=yyy|613=xxx|445=1=>[611=ggg|612=hhh|613=jjj]", str(grp))

    def testPickle(self):
        msg = FIXMessage("AB")
        msg.setField("45", "dgd")
        msg.setField("32", "aaaa")
        msg.setField("323", "bbbb")

        rptgrp1 = FIXContext()
        rptgrp1.setField("611", "aaa")
        rptgrp1.setField("612", "bbb")
        rptgrp1.setField("613", "ccc")

        msg.addRepeatingGroup("444", rptgrp1, 0)

        str = pickle.dumps(msg)

        msg2 = pickle.loads(str)
        self.assertEqual(msg, msg2)

if __name__ == '__main__':
    unittest.main()
