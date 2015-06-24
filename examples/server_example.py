import logging
from pyfix.connection import ConnectionState, MessageDirection
from pyfix.engine import FIXEngine
from pyfix.message import FIXMessage
from pyfix.server_connection import FIXServer
from pyfix.event import EventManager


class Server(FIXEngine):
    def __init__(self):
        FIXEngine.__init__(self, "server_example.store")
        # create a FIX Server using the FIX 4.4 standard
        self.server = FIXServer(self, "pyfix.FIX44")

        # we register some listeners since we want to know when the connection goes up or down
        self.server.addConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.server.addConnectionListener(self.onDisconnect, ConnectionState.DISCONNECTED)

        # start our event listener indefinitely
        self.server.start('', int("9898"))
        while True:
            self.eventManager.waitForEventWithTimeout(10.0)

        # some clean up before we shut down
        self.server.removeConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.server.removeConnectionListener(self.onConnect, ConnectionState.DISCONNECTED)

    def validateSession(self, targetCompId, senderCompId):
        logging.info("Received login request for %s / %s" % (senderCompId, targetCompId))
        return True

    def onConnect(self, session):
        logging.info("Accepted new connection from %s" % (session.address(), ))
        # register to receive message notifications on the session which has just been created
        session.addMessageHandler(self.onLogin, MessageDirection.OUTBOUND, self.server.protocol.msgtype.LOGON)
        session.addMessageHandler(self.onNewOrder, MessageDirection.INBOUND, self.server.protocol.msgtype.NEWORDERSINGLE)

    def onDisconnect(self, session):
        logging.info("%s has disconnected" % (session.address(), ))
        # we need to clean up our handlers, since this session is disconnected now
        session.removeMessageHandler(self.onLogin, MessageDirection.OUTBOUND, self.server.protocol.msgtype.LOGON)
        session.removeMessageHandler(self.onNewOrder, MessageDirection.INBOUND, self.server.protocol.msgtype.NEWORDERSINGLE)

    def onLogin(self, connectionHandler, msg):
        codec = connectionHandler.codec
        logging.info("We're logged in now")
        logging.info("[" + msg[codec.protocol.fixtags.SenderCompID] + "] <---- " + codec.protocol.msgtype.msgTypeToName(msg[codec.protocol.fixtags.MsgType]))

    def onNewOrder(self, connectionHandler, request):
        logging.debug("Received msg: %s" % (request,))
        # respond with an ExecutionReport Ack
        codec = connectionHandler.codec
        msg = FIXMessage(codec.protocol.msgtype.EXECUTIONREPORT)
        msg.setField(codec.protocol.fixtags.Price, request.getField(codec.protocol.fixtags.Price))
        msg.setField(codec.protocol.fixtags.OrderQty, request.getField(codec.protocol.fixtags.OrderQty))
        msg.setField(codec.protocol.fixtags.Symbol, request.getField(codec.protocol.fixtags.OrderQty))
        msg.setField(codec.protocol.fixtags.SecurityID, "GB00BH4HKS39")
        msg.setField(codec.protocol.fixtags.SecurityIDSource, "4")
        msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
        msg.setField(codec.protocol.fixtags.Account, "TEST")
        msg.setField(codec.protocol.fixtags.HandlInst, "1")
        msg.setField(codec.protocol.fixtags.ExecType, "0")
        msg.setField(codec.protocol.fixtags.LeavesQty, "0")
        msg.setField(codec.protocol.fixtags.Side, request.getField(codec.protocol.fixtags.Side))
        msg.setField(codec.protocol.fixtags.ClOrdID, request.getField(codec.protocol.fixtags.ClOrdID))
        msg.setField(codec.protocol.fixtags.Currency, "GBP")

        connectionHandler.sendMsg(msg)


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    server = Server()
    logging.info("All done... shutting down")

if __name__ == '__main__':
    main()
