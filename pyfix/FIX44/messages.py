from pyfix.FIX44 import msgtype, fixtags
from pyfix.message import FIXMessage

class Messages(object):

    @staticmethod
    def logon():
        msg = FIXMessage(msgtype.LOGON)
        msg.setField(fixtags.EncryptMethod, 0)
        msg.setField(fixtags.HeartBtInt, 30)
        return msg

    @staticmethod
    def logout():
        msg = FIXMessage(msgtype.LOGOUT)
        return msg

    @staticmethod
    def heartbeat():
        msg = FIXMessage(msgtype.HEARTBEAT)
        return msg

    @staticmethod
    def test_request():
        msg = FIXMessage(msgtype.TESTREQUEST)
        return msg

    @staticmethod
    def sequence_reset(respondingTo, isGapFill):
        msg = FIXMessage(msgtype.SEQUENCERESET)
        msg.setField(fixtags.GapFillFlag, 'Y' if isGapFill else 'N')
        msg.setField(fixtags.MsgSeqNum, respondingTo[fixtags.BeginSeqNo])
        return msg
    #
    # @staticmethod
    # def sequence_reset(beginSeqNo, endSeqNo, isGapFill):
    #     msg = FIXMessage(msgtype.SEQUENCERESET)
    #     msg.setField(fixtags.GapFillFlag, 'Y' if isGapFill else 'N')
    #     msg.setField(fixtags.MsgSeqNum, respondingTo[fixtags.BeginSeqNo])
    #     return msg


    @staticmethod
    def resend_request(beginSeqNo, endSeqNo = '0'):
        msg = FIXMessage(msgtype.RESENDREQUEST)
        msg.setField(fixtags.BeginSeqNo, str(beginSeqNo))
        msg.setField(fixtags.EndSeqNo, str(endSeqNo))
        return msg