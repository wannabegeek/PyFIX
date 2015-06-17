#! /usr/bin/env python

#
# Simple FIX Server
#
# Tom Fewster 2013
#

import asyncore
from datetime import datetime, timedelta
import importlib
import socket
import errno
from pyfix.codec import Codec

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

if os.name == 'posix':
    class ShutdownDispatcher(asyncore.file_dispatcher):
        def __init__(self, server):
            (self.pipein, self.pipeout) = os.pipe()
            asyncore.file_dispatcher.__init__(self, self.pipein)
            self.server = server

        def close(self):
            os.close(self.pipein)
            os.close(self.pipeout)

        def writable(self):
            return False

        def handle_read(self, type, closure):
            logging.info("Should I shutdown????")
            try:
                while True:
                    self.recv(1)
            except:
                pass
            self.server.signalShutdown()

        def signalShutdown(self):
            os.write(self.pipeout, "A".encode('utf-8'))
else:
    class ShutdownDispatcher(asyncore.dispatcher):
        def __init__(self, server):
            self.w = socket.socket()
            self.w.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.server = server

            count = 0
            while True:
                count += 1
                # Bind to a local port; for efficiency, let the OS pick
                # a free port for us.
                # Unfortunately, stress tests showed that we may not
                # be able to connect to that port ("Address already in
                # use") despite that the OS picked it.
                a = socket.socket()
                a.bind(("127.0.0.1", 0))
                connect_address = a.getsockname() # assigned (host, port) pair
                a.listen(1)
                try:
                    self.w.connect(connect_address)
                    break # success
                except socket.error as detail:
                    if detail[0] != errno.WSAEADDRINUSE:
                        # "Address already in use" is the only error
                        # I've seen on two WinXP Pro SP2 boxes, under
                        # Pythons 2.3.5 and 2.4.1.
                        raise
                    # (10048, 'Address already in use')
                    # assert count <= 2 # never triggered in Tim's tests
                    if count >= 10: # I've never seen it go above 2
                        a.close()
                        self.w.close()
                        raise RuntimeError("Cannot bind trigger!")
                    # Close `a` and try again.  Note:  I originally put a short
                    # sleep() here, but it didn't appear to help or hurt.
                    a.close()

            r, addr = a.accept() # r becomes asyncore's (self.)socket
            a.close()

            asyncore.dispatcher.__init__(self, r)

        def writable(self):
            return False

        def handle_read(self, type, closure):
            logging.info("Should I shutdown????")
            try:
                while True:
                    self.recv(1)
            except:
                pass
            self.server.signalShutdown()

        def signalShutdown(self):
            self.w.send("A".encode('utf-8'))

connectedSessions = {}

class FIXConnectionHandler(object):
    def __init__(self, eventMgr, protocol, sock=None, addr=None, observer=None):
        self.codec = Codec(protocol)
        self.eventMgr = eventMgr
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
        self.eventMgr.registerHandler(self.socketEvent)

    def address(self):
        return self.addr

    def disconnect(self):
        self.handle_close()

    def addMessageHandler(self, handler, direction = None, msgType = None):
        self.msgHandlers.append((handler, direction, msgType))

    def removeMsgHandler(self, handler, direction = None, msgType = None):
        remove = filter(lambda x: x[0] == handler and
                                  (x[1] == direction or direction is None) and
                                  (x[2] == msgType or msgType is None), self.msgHandlers)
        for h in remove:
            self.msgHandlers.remove(h)

    def calculateHeartbeatTimeout(self):
        if self.connectionState != ConnectionState.LOGGED_IN:
            return None
        return (self.heartbeatNextSchedule - datetime.datetime.utcnow()).total_seconds()

    def sendHeartbeat(self):
        msg = self.codec.pack(self.codec.protocol.messages.Messages.heartbeat(), self.session)
        self.sendMsg(msg)

    def expectedHeartbeat(self, type, closure):
        logging.warning("Expected heartbeat from peer %s" % (self.expectedHeartbeatRegistration ,))
        msg = self.codec.pack(self.codec.protocol.messages.Messages.test_request(), self.session)
        self.sendMsg(msg)

    def registerLoggedIn(self):
        self.heartbeatTimerRegistration = TimerEventRegistration(lambda type, closure: self.sendHeartbeat(), self.heartbeatPeriod)
        self.eventMgr.registerHandler(self.heartbeatTimerRegistration)
        # register timeout for 10% more than we expect
        self.expectedHeartbeatRegistration = TimerEventRegistration(self.expectedHeartbeat, self.heartbeatPeriod * 1.10)
        self.eventMgr.registerHandler(self.expectedHeartbeatRegistration)


    def registerLoggedOut(self):
        if self.heartbeatTimerRegistration is not None:
            self.eventMgr.unregisterHandler(self.heartbeatTimerRegistration)
            self.heartbeatTimerRegistration = None
        if self.expectedHeartbeatRegistration is not None:
            self.eventMgr.unregisterHandler(self.expectedHeartbeatRegistration)
            self.expectedHeartbeatRegistration = None

    def handle_read(self, type, closure):
        protocol = self.codec.protocol
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
            self.eventMgr.unregisterHandler(self.socketEvent)


    def sendMsg(self, msg):
        protocol = self.codec.protocol

        if self.connectionState != ConnectionState.CONNECTED and self.connectionState != ConnectionState.LOGGED_IN:
            raise FIXException(FIXException.FIXExceptionReason.NOT_CONNECTED)

        encodedMsg = msg.encode('utf-8')
        self.sock.send(encodedMsg)
        self.heartbeatNextSchedule = datetime.utcnow() + timedelta(seconds=self.heartbeatPeriod)
        (decodedMsg, empty) = self.codec.parse(encodedMsg)

        for handler in filter(lambda x: (x[1] is None or x[1] == MessageDirection.OUTBOUND) and
                (x[2] is None or x[2] == decodedMsg[protocol.fixtags.MsgType]), self.msgHandlers):
                handler[0](self, decodedMsg)


class FIXEndPoint(object):
    def __init__(self, eventMgr, protocol):
        self.eventMgr = eventMgr
        self.protocol = importlib.import_module(protocol)

        self.connections = []
        self.connectionHandlers = []
        (self.pipein, self.pipeout) = os.pipe()
        self.shutdown = ShutdownDispatcher(self)
        self.shouldShutdown = False

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

    def heartbeatScheduleTimeout(self):
        timeouts = []
        for connection in self.connections:
            timeout = connection.calculateHeartbeatTimeout()
            if timeout is not None:
                if timeout < 0:
                    if connection.connectionState == ConnectionState.LOGGED_IN:
                        connection.sendHeartbeat()
                    timeout = connection.calculateHeartbeatTimeout()
                timeouts.append(timeout)
        if timeouts == []:
            return None
        return min(timeouts)
