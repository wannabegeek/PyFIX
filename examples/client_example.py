import logging
import random
from pyfix.connection import ConnectionState, MessageDirection
from pyfix.client_connection import FIXClient
from pyfix.message import FIXMessage
from pyfix.event import EventManager, TimerEventRegistration

class Client:
    def __init__(self):
        self.clOrdID = 1

        self.eventMgr = EventManager()
        self.client = FIXClient(self.eventMgr, "pyfix.FIX44", "TARGET", "SENDER")

        self.client.addConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.client.addConnectionListener(self.onDisconnect, ConnectionState.DISCONNECTED)

        self.client.start('localhost', int("9898"))
        while True:
            self.eventMgr.waitForEventWithTimeout(10.0)

        self.client.removeConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.client.removeConnectionListener(self.onConnect, ConnectionState.DISCONNECTED)

    def onConnect(self, session):
        logging.info("Established connection to %s" % (session.address(), ))
        session.addMessageHandler(self.onLogin, MessageDirection.INBOUND, self.client.protocol.msgtype.LOGON)

    def onDisconnect(self, session):
        logging.info("%s has disconnected" % (session.address(), ))
        session.removeMsgHandler(self.onLogin, MessageDirection.INBOUND, self.client.protocol.msgtype.LOGON)
        if self.msgGenerator:
            self.eventMgr.unregisterHandler(self.msgGenerator)

    def sendOrder(self, connectionHandler):
        self.clOrdID = self.clOrdID + 1
        codec = connectionHandler.codec
        msg = FIXMessage(codec.protocol.msgtype.NEWORDERSINGLE)
        msg.setField(codec.protocol.fixtags.Price, random.random() * 1000)
        msg.setField(codec.protocol.fixtags.OrderQty, int(random.random() * 10000))
        msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
        msg.setField(codec.protocol.fixtags.SecurityID, "GB00BH4HKS39")
        msg.setField(codec.protocol.fixtags.SecurityIDSource, "4")
        msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
        msg.setField(codec.protocol.fixtags.Account, "TEST")
        msg.setField(codec.protocol.fixtags.HandlInst, "1")
        msg.setField(codec.protocol.fixtags.ExDestination, "XLON")
        msg.setField(codec.protocol.fixtags.Side, int(random.random() * 2))
        msg.setField(codec.protocol.fixtags.ClOrdID, str(self.clOrdID))
        msg.setField(codec.protocol.fixtags.Currency, "GBP")

        connectionHandler.sendMsg(codec.pack(msg, connectionHandler.session))


    def onLogin(self, connectionHandler, msg):
        logging.info("Logged in")

        # lets do something like send and order every 3 seconds
        self.msgGenerator = TimerEventRegistration(lambda type, closure: self.sendOrder(closure), 3.0, connectionHandler)
        self.eventMgr.registerHandler(self.msgGenerator)


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    client = Client()
    logging.info("All done... shutting down")

if __name__ == '__main__':
    main()
