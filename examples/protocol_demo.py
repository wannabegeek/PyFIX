import logging

class tag(object):
    def __init__(self, name, value, values):
        self.name = name
        self.value = value
        for k, v in values:
            setattr(self, k, v)

    def __eq__(self, other):
        if type(other) == tag:
            return other.name == self.name and other.value == self.value
        else:
            return self.value == other

    def __str__(self):
        return self.value

    def __hash__(self):
        return hash(self.name + self.value)

    __repr__ = __str__

class msgtype(object):
    pass

class tags(object):
    def __init__(self):
        self.tags = {}
        self._addTag("MsgType", "35", [("ExecutionReport", "8"), ("NewOrderSingle", "D")])

    def _addTag(self, key, value, values):
        t = tag(key, value, values)
        setattr(self, key, t)
        self.tags[t] = key

class Demo(object):
    def __init__(self):
        t =tags()
        logging.debug("%s = %s" % (t.tags[t.MsgType], t.MsgType))
        logging.debug("ExecutionReport: %s" % (t.MsgType.ExecutionReport,))

def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    server = Demo()
    logging.info("All done... shutting down")

if __name__ == '__main__':
    main()
