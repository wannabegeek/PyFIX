import logging
import socket
from pyfix.session import FIXSession
from pyfix.connection import FIXEndPoint, ConnectionState, MessageDirection, FIXConnectionHandler
from pyfix.event import FileDescriptorEventRegistration, EventType


class FIXServerConnectionHandler(FIXConnectionHandler):
    def __init__(self, engine, protocol, sock=None, addr=None, observer=None):
        FIXConnectionHandler.__init__(self, engine, protocol, sock, addr, observer)

    def processMessage(self, decodedMsg):
        protocol = self.codec.protocol

        recvSeqNo = decodedMsg[protocol.fixtags.MsgSeqNum]

        if self.connectionState != ConnectionState.LOGGED_IN:
            if decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGON:
                if self.connectionState == ConnectionState.LOGGED_IN:
                    logging.warning("Client session already logged in - ignoring login request")
                else :
                    session = FIXSession(self.sessionKey(decodedMsg), decodedMsg[protocol.fixtags.TargetCompID], decodedMsg[protocol.fixtags.SenderCompID])
                    if self.engine.validateSession(session):
                        self.session = session
                        self.connectionState = ConnectionState.LOGGED_IN
                        self.heartbeatPeriod = float(decodedMsg[protocol.fixtags.HeartBtInt])
                        self._notifyMessageObservers(decodedMsg, MessageDirection.INBOUND)

                        self.sendMsg(protocol.messages.Messages.logon())
                        self.registerLoggedIn()
                    else:
                        self.disconnect()
                        return # we have to return here since self.session won't be valid
            else:
                logging.warning("Can't process message, counterparty is not logged in")
                return # we have to return here since self.session won't be valid
        else:
            # we must be logged in to handle these messages
            if decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGON:
                logging.warning("Client session already logged in - ignoring login request")
            else:
                self._notifyMessageObservers(decodedMsg, MessageDirection.INBOUND)

                if decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGOUT:
                    self.connectionState = ConnectionState.LOGGED_OUT
                    self.registerLoggedOut()
                    self.handle_close()
                elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.TESTREQUEST:
                    self.sendMsg(protocol.messages.Messages.heartbeat())
                elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.RESENDREQUEST:
                    self.sendMsg(protocol.messages.Messages.sequence_reset(decodedMsg, True))
                elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.SEQUENCERESET:
                    newSeqNo = decodedMsg[protocol.fixtags.NewSeqNo]
                    recvSeqNo = newSeqNo

        # validate the seq number
        (seqNoState, lastKnownSeqNo) = self.session.validateRecvSeqNo(recvSeqNo)

        if seqNoState is False:
            # We should send a resend request
            self.sendMsg(protocol.messages.Messages.resend_request(lastKnownSeqNo, recvSeqNo))
        else:
            self.session.setRecvSeqNo(recvSeqNo)

class FIXServer(FIXEndPoint):
    def __init__(self, engine, protocol):
     FIXEndPoint.__init__(self, engine, protocol)

    def start(self, host, port):
        self.connections = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.serverSocketRegistration = FileDescriptorEventRegistration(self.handle_accept, self.socket, EventType.READ)

        logging.debug("Awaiting Connections " + host + ":" + str(port))
        self.engine.eventManager.registerHandler(self.serverSocketRegistration)

    def stop(self):
        logging.info("Stopping server connections")
        for connection in self.connections:
            connection.disconnect()
        self.serverSocketRegistration.fd.close()
        self.engine.eventManager.unregisterHandler(self.serverSocketRegistration)

    def handle_accept(self, type, closure):
        pair = self.socket.accept()
        if pair is not None:
            sock, addr = pair
            logging.info("Connection from %s" % repr(addr))
            connection = FIXServerConnectionHandler(self.engine, self.protocol, sock, addr, self)
            self.connections.append(connection)
            for handler in filter(lambda x: x[1] == ConnectionState.CONNECTED, self.connectionHandlers):
                    handler[0](connection)
