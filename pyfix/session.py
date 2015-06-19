#
# Simple FIX Server
#
# Tom Fewster 2013
#
import logging

import os
import mmap

class FIXSession:

    def __init__(self, senderCompId, targetCompId):
        self.senderCompId = senderCompId
        self.targetCompId = targetCompId
        filename = self.senderCompId + "_" + self.targetCompId + ".seq"
        exists = os.path.exists(filename)
        f = open(filename, "a+")
        if not exists:
            f.write('000001:000001')
            f.flush()
        f.seek(0)
        self.mm = mmap.mmap(f.fileno(), 13)
        seqNos = self.mm.read(13).decode('utf-8')
        if seqNos:
            (sndSeqNum, rcvSeqNum) = seqNos.split(':')
            self.sndSeqNum = int(sndSeqNum)
            self.rcvSeqNum = int(rcvSeqNum)
            #print 'Snd:%d Rcv:%d' % (self.sndSeqNum, self.rcvSeqNum)

    def __del__(self):
        self.mm.flush()
        self.mm.close()

    def allocateSndSeqNo(self):
        result = self.sndSeqNum
        self.sndSeqNum += 1
        self.mm.seek(0)
        newSeqNoValues = '%06d:%06d' % (self.sndSeqNum, self.rcvSeqNum)
        self.mm.write(newSeqNoValues.encode('utf-8'))
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
        self.mm.seek(0)
        newSeqNoValues = '%06d:%06d' % (self.sndSeqNum, self.rcvSeqNum)
        self.mm.write(newSeqNoValues.encode('utf-8'))

