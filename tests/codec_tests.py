import importlib
import datetime
import mock as mock
from pyfix.codec import Codec
from pyfix.message import FIXMessage, FIXContext

__author__ = 'tom'

import unittest

class FakeDate(datetime.datetime):
    @classmethod
    def utcnow(cls):
        return cls(2015, 6, 19, 11, 8, 54)

class FIXCodecTests(unittest.TestCase):
    def testDecode(self):
        protocol = importlib.import_module("pyfix.FIX44")
        codec = Codec(protocol)
        inMsg = b'8=FIX.4.4\x019=817\x0135=J\x0134=953\x0149=FIX_ALAUDIT\x0156=BFUT_ALAUDIT\x0143=N\x0152=20150615-09:21:42.459\x0170=00000002664ASLO1001\x01626=2\x0110626=5\x0171=0\x0160=20150615-10:21:42\x01857=1\x0173=1\x0111=00000006321ORLO1\x0138=100.0\x01800=100.0\x01124=1\x0132=100.0\x0117=00000009758TRLO1\x0131=484.50\x0154=2\x0153=100.0\x0155=FTI\x01207=XEUE\x01454=1\x01455=EOM5\x01456=A\x01200=201506\x01541=20150619\x01461=FXXXXX\x016=484.50\x0174=2\x0175=20150615\x0178=2\x0179=TEST123\x0130009=12345\x01467=00000014901CALO1001\x019520=00000014898CALO1\x0180=33.0\x01366=484.50\x0181=0\x01153=484.50\x0110626=5\x0179=TEST124\x0130009=12345\x01467=00000014903CALO1001\x019520=00000014899CALO1\x0180=67.0\x01366=484.50\x0181=0\x01153=484.50\x0110626=5\x01453=3\x01448=TEST1\x01447=D\x01452=3\x01802=2\x01523=12345\x01803=3\x01523=TEST1\x01803=19\x01448=TEST1WA\x01447=D\x01452=38\x01802=4\x01523=Test1 Wait\x01803=10\x01523= \x01803=26\x01523=\x01803=3\x01523=TestWaCRF2\x01803=28\x01448=hagap\x01447=D\x01452=11\x01802=2\x01523=GB\x01803=25\x01523=BarCapFutures.FETService\x01803=24\x0110=033\x01'
        msg, remaining = codec.decode(inMsg)

        self.assertEqual("8=FIX.4.4|9=817|35=J|34=953|49=FIX_ALAUDIT|56=BFUT_ALAUDIT|43=N|52=20150615-09:21:42.459|70=00000002664ASLO1001|626=2|10626=5|71=0|60=20150615-10:21:42|857=1|73=1=>[11=00000006321ORLO1|38=100.0|800=100.0]|124=1=>[32=100.0|17=00000009758TRLO1|31=484.50]|54=2|53=100.0|55=FTI|207=XEUE|454=1=>[455=EOM5|456=A]|200=201506|541=20150619|461=FXXXXX|6=484.50|74=2|75=20150615|78=1=>[79=TEST123]|30009=12345|467=00000014903CALO1001|9520=00000014899CALO1|80=67.0|366=484.50|81=0|153=484.50|79=TEST124|453=3=>[448=TEST1|447=D|452=3|802=2=>[523=12345|803=3, 523=TEST1|803=19], 448=TEST1WA|447=D|452=38|802=4=>[523=Test1 Wait|803=10, 523= |803=26, 523=|803=3, 523=TestWaCRF2|803=28], 448=hagap|447=D|452=11|802=2=>[523=GB|803=25, 523=BarCapFutures.FETService|803=24]]|10=033", str(msg))

    @mock.patch("pyfix.codec.datetime", FakeDate)
    def testEncode(self):
        from datetime import datetime

        print("%s" % (datetime.utcnow()))

        mock_session = mock.Mock()
        mock_session.senderCompId = "sender"
        mock_session.targetCompId = "target"
        mock_session.allocateSndSeqNo.return_value = 1

        protocol = importlib.import_module("pyfix.FIX44")
        codec = Codec(protocol)

        msg = FIXMessage(codec.protocol.msgtype.NEWORDERSINGLE)
        msg.setField(codec.protocol.fixtags.Price, "123.45")
        msg.setField(codec.protocol.fixtags.OrderQty, 9876)
        msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
        msg.setField(codec.protocol.fixtags.SecurityID, "GB00BH4HKS39")
        msg.setField(codec.protocol.fixtags.SecurityIDSource, "4")
        msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
        msg.setField(codec.protocol.fixtags.Account, "TEST")
        msg.setField(codec.protocol.fixtags.HandlInst, "1")
        msg.setField(codec.protocol.fixtags.ExDestination, "XLON")
        msg.setField(codec.protocol.fixtags.Side, 1)
        msg.setField(codec.protocol.fixtags.ClOrdID, "abcdefg")
        msg.setField(codec.protocol.fixtags.Currency, "GBP")

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

        result = codec.encode(msg, mock_session)
        expected = '8=FIX.4.4\x019=201\x0135=D\x0149=sender\x0156=target\x0134=1\x0152=20150619-11:08:54.000\x0144=123.45\x0138=9876\x0155=VOD.L\x0148=GB00BH4HKS39\x0122=4\x011=TEST\x0121=1\x01100=XLON\x0154=1\x0111=abcdefg\x0115=GBP\x01444=2\x01611=aaa\x01612=bbb\x01613=ccc\x01611=zzz\x01612=yyy\x01613=xxx\x0110=255\x01'
        self.assertEqual(expected, result)


if __name__ == '__main__':
    unittest.main()

