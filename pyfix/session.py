import logging

import os
import mmap

class FIXSession:
    def __init__(self, targetCompId, senderCompId):
        self.key = FIXSession.generateKeysFromCompIds(targetCompId, senderCompId)
        self.senderCompId = senderCompId
        self.targetCompId = targetCompId

        self.sndSeqNum = 1
        self.rcvSeqNum = 1

    @classmethod
    def generateKeysFromCompIds(cls, targetCompId, senderCompId):
        return "%s_%s" % (senderCompId, targetCompId)

    def validateCompIds(self, targetCompId, senderCompId):
        return self.senderCompId == senderCompId and self.targetCompId == targetCompId

    def allocateSndSeqNo(self):
        result = self.sndSeqNum
        self.sndSeqNum += 1
        return str(result)

    def validateRecvSeqNo(self, seqNo):
        if self.rcvSeqNum < int(seqNo):
            logging.warning("SeqNum from client unexpected (Rcvd:" + seqNo + " Expected:" + str(self.rcvSeqNum) + ")")
            return (False, self.rcvSeqNum)
        else:
            return (True, seqNo)

    def setRecvSeqNo(self, seqNo):
        if self.rcvSeqNum != int(seqNo):
            logging.warning("SeqNum from client unexpected (Rcvd:" + seqNo + " Expected:" + str(self.rcvSeqNum) + ")")
        self.rcvSeqNum = int(seqNo) + 1

