
class TransactionResource(object):
    def __init__(self, action):
        self.action = action

    def commit(self):
        if self.action != None:
            self.action()

class Transaction(TransactionResource):

    def __init__(self):
        self.resources = []
        TransactionResource.__init__(self, None)

    def addResource(self, resource):
        self.resources.append(resource)
        pass

    def commit(self):
        for resource in self.resources:
            resource.commit()

class PriorityTransaction(TransactionResource):
    def __init__(self):
        self.resources = []
        TransactionResource.__init__(self, None)

    def addResource(self, resource, priority):
        self.resources.append((priority, resource))

    def commit(self):
        # TODO: sort the resources...
        # High --> Low (so you can always make something higher priority)
        for resource in self.resources:
            resource.commit()
