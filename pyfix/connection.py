from datetime import datetime, timedelta
import importlib
from pyfix.codec import Codec
from pyfix.journaler import DuplicateSeqNoError
from pyfix.message import FIXMessage

from pyfix.session import *
from enum import Enum
from pyfix.event import FileDescriptorEventRegistration, EventType, TimerEventRegistration

class ConnectionState(Enum):
    UNKNOWN = 0
    DISCONNECTED = 1
    CONNECTED = 2
    LOGGED_IN = 3
    LOGGED_OUT = 4

class MessageDirection(Enum):
    INBOUND = 0
    OUTBOUND = 1

class FIXException(Exception):
    class FIXExceptionReason(Enum):
        NOT_CONNECTED = 0
        DECODE_ERROR = 1
        ENCODE_ERROR = 2

    def __init__(self, reason, description = None):
        super(Exception, self).__init__(description)
        self.reason = reason

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

    def sessionKey(self, context):
        if type(context) is FIXMessage:
            return "%s_%s" % (context[self.codec.protocol.fixtags.SenderCompID], context[self.codec.protocol.fixtags.TargetCompID])
        elif type(context) is FIXSession:
            return "%s_%s" % (context.senderCompID, context.targetCompID)
        else:
            raise RuntimeError("Can't generate session key from object")

    def sessionKeyFromCompIds(self, targetCompId, senderCompId):
        return "%s_%s" % (senderCompId, targetCompId)

    def address(self):
        return self.addr

    def disconnect(self):
        self.handle_close()

    def _notifyMessageObservers(self, msg, direction):
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

    def sendHeartbeat(self):
        self.sendMsg(self.codec.protocol.messages.Messages.heartbeat())

    def expectedHeartbeat(self, type, closure):
        logging.warning("Expected heartbeat from peer %s" % (self.expectedHeartbeatRegistration ,))
        self.sendMsg(self.codec.protocol.messages.Messages.test_request())

    def registerLoggedIn(self):
        self.heartbeatTimerRegistration = TimerEventRegistration(lambda type, closure: self.sendHeartbeat(), self.heartbeatPeriod)
        self.engine.eventManager.registerHandler(self.heartbeatTimerRegistration)
        # register timeout for 10% more than we expect
        self.expectedHeartbeatRegistration = TimerEventRegistration(self.expectedHeartbeat, self.heartbeatPeriod * 1.10)
        self.engine.eventManager.registerHandler(self.expectedHeartbeatRegistration)


    def registerLoggedOut(self):
        if self.heartbeatTimerRegistration is not None:
            self.engine.eventManager.unregisterHandler(self.heartbeatTimerRegistration)
            self.heartbeatTimerRegistration = None
        if self.expectedHeartbeatRegistration is not None:
            self.engine.eventManager.unregisterHandler(self.expectedHeartbeatRegistration)
            self.expectedHeartbeatRegistration = None

    def handle_read(self, type, closure):
        protocol = self.codec.protocol
        try:
            msg = self.sock.recv(8192)
            if msg:
                self.msgBuffer = self.msgBuffer + msg
                (decodedMsg, parsedLength) = self.codec.parse(self.msgBuffer)
                self.msgBuffer = self.msgBuffer[parsedLength:]
                while decodedMsg is not None and self.connectionState != ConnectionState.DISCONNECTED:
                    self.processMessage(decodedMsg)
                    (decodedMsg, parsedLength) = self.codec.parse(self.msgBuffer)
                    self.msgBuffer = self.msgBuffer[parsedLength:]
                if self.expectedHeartbeatRegistration is not None:
                    self.expectedHeartbeatRegistration.reset()
            else:
                logging.debug("Connection has been closed")
                self.disconnect()
        except ConnectionError as why:
                logging.debug("Connection has been closed %s" % (why, ))
                self.disconnect()

    def processMessage(self, msg):
        pass

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

        encodedMsg = self.codec.pack(msg, self.session).encode('utf-8')
        self.sock.send(encodedMsg)
        if self.heartbeatTimerRegistration is not None:
            self.heartbeatTimerRegistration.reset()

        decodedMsg, junk = self.codec.parse(encodedMsg)

        try:
            self._notifyMessageObservers(decodedMsg, MessageDirection.OUTBOUND)
        except DuplicateSeqNoError:
            logging.error("We have sent a message with a duplicate seq no, failed to persist it")


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

