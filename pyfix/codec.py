from datetime import datetime
import logging
from pyfix.message import FIXMessage, FIXContext

class EncodingError(Exception):
    pass

class DecodingError(Exception):
    pass

class RepeatingGroupContext(FIXContext):
    def __init__(self, tag, repeatingGroupTags, parent):
        self.tag = tag
        self.repeatingGroupTags = repeatingGroupTags
        self.parent = parent
        FIXContext.__init__(self)

class Codec(object):
    def __init__(self, protocol):
        self.protocol = protocol
        self.SOH = '\x01'

    @staticmethod
    def current_datetime():
        return datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]

    def _addTag(self, body, t, msg):
        if msg.isRepeatingGroup(t):
            count, groups = msg.getRepeatingGroup(t)
            body.append("%s=%s" % (t, count))
            for group in groups:
                for tag in group.tags:
                    self._addTag(body, tag, group)
        else:
            body.append("%s=%s" % (t, msg[t]))

    def encode(self, msg, session):
        # Create body
        body = []

        msgType = msg.msgType

        body.append("%s=%s" % (self.protocol.fixtags.SenderCompID, session.senderCompId))
        body.append("%s=%s" % (self.protocol.fixtags.TargetCompID, session.targetCompId))

        seqNo = 0
        if msgType == self.protocol.msgtype.SEQUENCERESET:
            if self.protocol.fixtags.GapFillFlag in msg and msg[self.protocol.fixtags.GapFillFlag] == "Y":
                # in this case the sequence number should already be on the message
                try:
                    seqNo = msg[self.protocol.fixtags.MsgSeqNum]
                except KeyError:
                    raise EncodingError("SequenceReset with GapFill='Y' must have the MsgSeqNum already populated")
            else:
                msg[self.protocol.fixtags.NewSeqNo] = session.allocateSndSeqNo()
                seqNo = msg[self.protocol.fixtags.MsgSeqNum]
        else:
            # if we have the PossDupFlag set, we need to send the message with the same seqNo
            if self.protocol.fixtags.PossDupFlag in msg and msg[self.protocol.fixtags.PossDupFlag] == "Y":
                try:
                    seqNo = msg[self.protocol.fixtags.MsgSeqNum]
                except KeyError:
                    raise EncodingError("Failed to encode message with PossDupFlay=Y but no previous MsgSeqNum")
            else:
                seqNo = session.allocateSndSeqNo()

        body.append("%s=%s" % (self.protocol.fixtags.MsgSeqNum, seqNo))
        body.append("%s=%s" % (self.protocol.fixtags.SendingTime, self.current_datetime()))

        for t in msg.tags:
            self._addTag(body, t, msg)

        # Enable easy change when debugging
        SEP = self.SOH

        body = self.SOH.join(body) + self.SOH

        # Create header
        header = []
        msgType = "%s=%s" % (self.protocol.fixtags.MsgType, msgType)
        header.append("%s=%s" % (self.protocol.fixtags.BeginString, self.protocol.beginstring))
        header.append("%s=%i" % (self.protocol.fixtags.BodyLength, len(body) + len(msgType) + 1))
        header.append(msgType)

        fixmsg = self.SOH.join(header) + self.SOH + body

        cksum = sum([ord(i) for i in list(fixmsg)]) % 256
        fixmsg = fixmsg + "%s=%0.3i" % (self.protocol.fixtags.CheckSum, cksum)

        #print len(fixmsg)

        return fixmsg + SEP

    def decode(self, rawmsg):
        #msg = rawmsg.rstrip(os.linesep).split(SOH)
        try:
            rawmsg = rawmsg.decode('utf-8')
            msg = rawmsg.split(self.SOH)
            msg = msg[:-1]

            if len(msg) < 3: # at a minumum we require BeginString, BodyLength & Checksum
                return (None, 0)

            tag, value = msg[0].split('=', 1)
            if tag != self.protocol.fixtags.BeginString:
                logging.error("*** BeginString missing or not 1st field *** [" + tag + "]")
            elif value != self.protocol.beginstring:
                logging.error("FIX Version unexpected (Recv: %s Expected: %s)" % (value, self.protocol.beginstring))

            tag, value = msg[1].split('=', 1)
            msgLength = len(msg[0]) + len(msg[1]) + len('10=000') + 3
            if tag != self.protocol.fixtags.BodyLength:
                logging.error("*** BodyLength missing or not 2nd field *** [" + tag + "]")
            else:
                msgLength += int(value)

            # do we have a complete message on the sockt
            if msgLength > len(rawmsg):
                return (None, 0)
            else:
                remainingMsgFragment = msgLength

                # resplit our message
                msg = rawmsg[:msgLength].split(self.SOH)
                msg = msg[:-1]
                decodedMsg = FIXMessage("UNKNOWN")

                # logging.debug("\t-----------------------------------------")
                # logging.debug("\t" + "|".join(msg))

                repeatingGroups = []
                repeatingGroupTags = self.protocol.fixtags.repeatingGroupIdentifiers()
                currentContext = decodedMsg

                for m in msg:
                    tag, value = m.split('=', 1)
                    t = None
                    try:
                        t = self.protocol.fixtags.tagToName(tag)
                    except KeyError:
                        logging.info("\t%s(Unknown): %s" % (tag, value))
                        t = "{unknown}"

                    if tag == self.protocol.fixtags.CheckSum:
                        cksum = ((sum([ord(i) for i in list(self.SOH.join(msg[:-1]))]) + 1) % 256)
                        if cksum != int(value):
                            logging.warning("\tCheckSum: %s (INVALID) expecting %s" % (int(value), cksum))
                    elif tag == self.protocol.fixtags.MsgType:
                        try:
                            msgType =  self.protocol.msgtype.msgTypeToName(value)
                            decodedMsg.setMsgType(value)
                        except KeyError:
                            logging.error('*** MsgType "%s" not supported ***')

                    if tag in repeatingGroupTags: # found the start of a repeating group
                        if type(currentContext) is RepeatingGroupContext: # i.e. we are already in a repeating group
                            while repeatingGroups and tag not in currentContext.repeatingGroupTags:
                                currentContext.parent.addRepeatingGroup(currentContext.tag, currentContext)
                                currentContext = currentContext.parent
                                del repeatingGroups[-1] # pop the completed group off the stack

                        ctx = RepeatingGroupContext(tag, repeatingGroupTags[tag], currentContext)
                        repeatingGroups.append(ctx)
                        currentContext = ctx
                    elif repeatingGroups: # we have 1 or more repeating groups in progress & our tag isn't the start of a group
                        while repeatingGroups and tag not in currentContext.repeatingGroupTags:
                            currentContext.parent.addRepeatingGroup(currentContext.tag, currentContext)
                            currentContext = currentContext.parent
                            del repeatingGroups[-1] # pop the completed group off the stack

                        if tag in currentContext.tags:
                            # if the repeating group already contains this field, start the next
                            currentContext.parent.addRepeatingGroup(currentContext.tag, currentContext)
                            ctx = RepeatingGroupContext(currentContext.tag, currentContext.repeatingGroupTags, currentContext.parent)
                            del repeatingGroups[-1] # pop the completed group off the stack
                            repeatingGroups.append(ctx)
                            currentContext = ctx

                        # else add it to the current one
                        currentContext.setField(tag, value)
                    else:
                        # this isn't a repeating group field, so just add it normally
                        decodedMsg.setField(tag, value)

                return (decodedMsg, remainingMsgFragment)
        except UnicodeDecodeError as why:
            logging.error("Failed to parse message %s" % (why, ))
            return (None, 0)
