import logging

class FIXSession:
    def __init__(self, key, targetCompId, senderCompId):
        self.key = key
        self.senderCompId = senderCompId
        self.targetCompId = targetCompId

        self.sndSeqNum = 0
        self.nextExpectedMsgSeqNum = 1

    def validateCompIds(self, targetCompId, senderCompId):
        return self.senderCompId == senderCompId and self.targetCompId == targetCompId

    def allocateSndSeqNo(self):
        self.sndSeqNum += 1
        return str(self.sndSeqNum)

    def validateRecvSeqNo(self, seqNo):
        if self.nextExpectedMsgSeqNum < int(seqNo):
            logging.warning("SeqNum from client unexpected (Rcvd: %s Expected: %s)" % (seqNo, self.nextExpectedMsgSeqNum))
            return (False, self.nextExpectedMsgSeqNum)
        else:
            return (True, seqNo)

    def setRecvSeqNo(self, seqNo):
        # if self.nextExpectedMsgSeqNum != int(seqNo):
        #     logging.warning("SeqNum from client unexpected (Rcvd: %s Expected: %s)" % (seqNo, self.nextExpectedMsgSeqNum))
        self.nextExpectedMsgSeqNum = int(seqNo) + 1

