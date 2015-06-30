import importlib
import sys
from pyfix.codec import Codec
from pyfix.journaler import DuplicateSeqNoError
from pyfix.message import FIXMessage, MessageDirection

from pyfix.session import *
from enum import Enum
from pyfix.event import FileDescriptorEventRegistration, EventType, TimerEventRegistration

class ConnectionState(Enum):
    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTED = 2
    LOGGED_IN = 3
    LOGGED_OUT = 4

class FIXException(Exception):
    class FIXExceptionReason(Enum):
        NOT_CONNECTED = 0
        DECODE_ERROR = 1
        ENCODE_ERROR = 2

    def __init__(self, reason, description = None):
        super(Exception, self).__init__(description)
        self.reason = reason

class SessionWarning(Exception):
    pass

class SessionError(Exception):
    pass

class FIXConnectionHandler(object):
    def __init__(self, engine, protocol, sock=None, addr=None, observer=None):
        self.codec = Codec(protocol)
        self.engine = engine
        self.connectionState = ConnectionState.CONNECTED
        self.session = None
        self.addr = addr
        self.observer = observer
        self.msgBuffer = b''
        self.heartbeatPeriod = 30.0
        self.msgHandlers = []
        self.sock = sock
        self.heartbeatTimerRegistration = None
        self.expectedHeartbeatRegistration = None
        self.socketEvent = FileDescriptorEventRegistration(self.handle_read, sock, EventType.READ)
        self.engine.eventManager.registerHandler(self.socketEvent)

    def address(self):
        return self.addr

    def disconnect(self):
        self.handle_close()

    def _notifyMessageObservers(self, msg, direction, persistMessage=True):
        if persistMessage is True:
            self.engine.journaller.persistMsg(msg, self.session, direction)
        for handler in filter(lambda x: (x[1] is None or x[1] == direction) and (x[2] is None or x[2] == msg.msgType), self.msgHandlers):
            handler[0](self, msg)

    def addMessageHandler(self, handler, direction = None, msgType = None):
        self.msgHandlers.append((handler, direction, msgType))

    def removeMessageHandler(self, handler, direction = None, msgType = None):
        remove = filter(lambda x: x[0] == handler and
                                  (x[1] == direction or direction is None) and
                                  (x[2] == msgType or msgType is None), self.msgHandlers)
        for h in remove:
            self.msgHandlers.remove(h)

    def _sendHeartbeat(self):
        self.sendMsg(self.codec.protocol.messages.Messages.heartbeat())

    def _expectedHeartbeat(self, type, closure):
        logging.warning("Expected heartbeat from peer %s" % (self.expectedHeartbeatRegistration ,))
        self.sendMsg(self.codec.protocol.messages.Messages.test_request())

    def registerLoggedIn(self):
        self.heartbeatTimerRegistration = TimerEventRegistration(lambda type, closure: self._sendHeartbeat(), self.heartbeatPeriod)
        self.engine.eventManager.registerHandler(self.heartbeatTimerRegistration)
        # register timeout for 10% more than we expect
        self.expectedHeartbeatRegistration = TimerEventRegistration(self._expectedHeartbeat, self.heartbeatPeriod * 1.10)
        self.engine.eventManager.registerHandler(self.expectedHeartbeatRegistration)


    def registerLoggedOut(self):
        if self.heartbeatTimerRegistration is not None:
            self.engine.eventManager.unregisterHandler(self.heartbeatTimerRegistration)
            self.heartbeatTimerRegistration = None
        if self.expectedHeartbeatRegistration is not None:
            self.engine.eventManager.unregisterHandler(self.expectedHeartbeatRegistration)
            self.expectedHeartbeatRegistration = None

    def _handleResendRequest(self, msg):
        protocol = self.codec.protocol
        responses = []

        beginSeqNo = msg[protocol.fixtags.BeginSeqNo]
        endSeqNo = msg[protocol.fixtags.EndSeqNo]
        if int(endSeqNo) == 0:
            endSeqNo = sys.maxsize
        logging.info("Received resent request from %s to %s", beginSeqNo, endSeqNo)
        replayMsgs = self.engine.journaller.recoverMsgs(self.session, MessageDirection.OUTBOUND, beginSeqNo, endSeqNo)
        gapFillBegin = int(beginSeqNo)
        gapFillEnd = int(beginSeqNo)
        for replayMsg in replayMsgs:
            msgSeqNum = int(replayMsg[protocol.fixtags.MsgSeqNum])
            if replayMsg[protocol.fixtags.MsgType] in protocol.msgtype.sessionMessageTypes:
                gapFillEnd = msgSeqNum + 1
            else:
                if self.engine.shouldResendMessage(self.session, replayMsg):
                    if gapFillBegin < gapFillEnd:
                        # we need to send a gap fill message
                        gapFillMsg = FIXMessage(protocol.msgtype.SEQUENCERESET)
                        gapFillMsg.setField(protocol.fixtags.GapFillFlag, 'Y')
                        gapFillMsg.setField(protocol.fixtags.MsgSeqNum, gapFillBegin)
                        gapFillMsg.setField(protocol.fixtags.NewSeqNo, str(gapFillEnd))
                        responses.append(gapFillMsg)

                    # and then resent the replayMsg
                    replayMsg.removeField(protocol.fixtags.BeginString)
                    replayMsg.removeField(protocol.fixtags.BodyLength)
                    replayMsg.removeField(protocol.fixtags.SendingTime)
                    replayMsg.removeField(protocol.fixtags.SenderCompID)
                    replayMsg.removeField(protocol.fixtags.TargetCompID)
                    replayMsg.removeField(protocol.fixtags.CheckSum)
                    replayMsg.setField(protocol.fixtags.PossDupFlag, "Y")
                    responses.append(replayMsg)

                    gapFillBegin = msgSeqNum + 1
                else:
                    gapFillEnd = msgSeqNum + 1
                    responses.append(replayMsg)

        if gapFillBegin < gapFillEnd:
            # we need to send a gap fill message
            gapFillMsg = FIXMessage(protocol.msgtype.SEQUENCERESET)
            gapFillMsg.setField(protocol.fixtags.GapFillFlag, 'Y')
            gapFillMsg.setField(protocol.fixtags.MsgSeqNum, gapFillBegin)
            gapFillMsg.setField(protocol.fixtags.NewSeqNo, str(gapFillEnd))
            responses.append(gapFillMsg)

        return responses

    def handle_read(self, type, closure):
        protocol = self.codec.protocol
        try:
            msg = self.sock.recv(8192)
            if msg:
                self.msgBuffer = self.msgBuffer + msg
                (decodedMsg, parsedLength) = self.codec.decode(self.msgBuffer)
                self.msgBuffer = self.msgBuffer[parsedLength:]
                while decodedMsg is not None and self.connectionState != ConnectionState.DISCONNECTED:
                    self.processMessage(decodedMsg)
                    (decodedMsg, parsedLength) = self.codec.decode(self.msgBuffer)
                    self.msgBuffer = self.msgBuffer[parsedLength:]
                if self.expectedHeartbeatRegistration is not None:
                    self.expectedHeartbeatRegistration.reset()
            else:
                logging.debug("Connection has been closed")
                self.disconnect()
        except ConnectionError as why:
                logging.debug("Connection has been closed %s" % (why, ))
                self.disconnect()

    def handleSessionMessage(self, msg):
        return -1

    def processMessage(self, decodedMsg):
        protocol = self.codec.protocol

        beginString = decodedMsg[protocol.fixtags.BeginString]
        if beginString != protocol.beginstring:
            logging.warning("FIX BeginString is incorrect (expected: %s received: %s)", (protocol.beginstring, beginString))
            self.disconnect()
            return

        msgType = decodedMsg[protocol.fixtags.MsgType]

        try:
            responses = []
            if msgType in protocol.msgtype.sessionMessageTypes:
                (recvSeqNo, responses) = self.handleSessionMessage(decodedMsg)
            else:
                recvSeqNo = decodedMsg[protocol.fixtags.MsgSeqNum]

            # validate the seq number
            (seqNoState, lastKnownSeqNo) = self.session.validateRecvSeqNo(recvSeqNo)

            if seqNoState is False:
                # We should send a resend request
                logging.info("Requesting resend of messages: %s to %s" % (lastKnownSeqNo, 0))
                responses.append(protocol.messages.Messages.resend_request(lastKnownSeqNo, 0))
                # we still need to notify if we are processing Logon message
                if msgType == protocol.msgtype.LOGON:
                    self._notifyMessageObservers(decodedMsg, MessageDirection.INBOUND, False)
            else:
                self.session.setRecvSeqNo(recvSeqNo)
                self._notifyMessageObservers(decodedMsg, MessageDirection.INBOUND)


            for m in responses:
                self.sendMsg(m)

        except SessionWarning as sw:
            logging.warning(sw)
        except SessionError as se:
            logging.error(se)
            self.disconnect()
        except DuplicateSeqNoError:
            try:
                if decodedMsg[protocol.fixtags.PossDupFlag] == "Y":
                    logging.debug("Received duplicate message with PossDupFlag set")
            except KeyError:
                pass
            finally:
                logging.error("Failed to process message with duplicate seq no (MsgSeqNum: %s) (and no PossDupFlag='Y') - disconnecting" % (recvSeqNo, ))
                self.disconnect()


    def handle_close(self):
        if self.connectionState != ConnectionState.DISCONNECTED:
            logging.info("Client disconnected")
            self.registerLoggedOut()
            self.sock.close()
            self.connectionState = ConnectionState.DISCONNECTED
            self.msgHandlers.clear()
            if self.observer is not None:
                self.observer.notifyDisconnect(self)
            self.engine.eventManager.unregisterHandler(self.socketEvent)


    def sendMsg(self, msg):
        if self.connectionState != ConnectionState.CONNECTED and self.connectionState != ConnectionState.LOGGED_IN:
            raise FIXException(FIXException.FIXExceptionReason.NOT_CONNECTED)

        encodedMsg = self.codec.encode(msg, self.session).encode('utf-8')
        self.sock.send(encodedMsg)
        if self.heartbeatTimerRegistration is not None:
            self.heartbeatTimerRegistration.reset()

        decodedMsg, junk = self.codec.decode(encodedMsg)

        try:
            self._notifyMessageObservers(decodedMsg, MessageDirection.OUTBOUND)
        except DuplicateSeqNoError:
            logging.error("We have sent a message with a duplicate seq no, failed to persist it (MsgSeqNum: %s)" % (decodedMsg[self.codec.protocol.fixtags.MsgSeqNum]))


class FIXEndPoint(object):
    def __init__(self, engine, protocol):
        self.engine = engine
        self.protocol = importlib.import_module(protocol)

        self.connections = []
        self.connectionHandlers = []

    def writable(self):
        return True

    def start(self, host, port):
        pass

    def stop(self):
        pass

    def addConnectionListener(self, handler, filter):
        self.connectionHandlers.append((handler, filter))

    def removeConnectionListener(self, handler, filter):
        for s in self.connectionHandlers:
            if s == (handler, filter):
                self.connectionHandlers.remove(s)

    def notifyDisconnect(self, connection):
        self.connections.remove(connection)
        for handler in filter(lambda x: x[1] == ConnectionState.DISCONNECTED, self.connectionHandlers):
                handler[0](connection)

