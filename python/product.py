class Product:
    def __init__(self, id, item):
        self.id = id
        self.bitPattern = item
        self.flag = False
        self.frequency = 0
        self.delayCountAND = 0
        self.delayCountXOR = 0
        self.length = 0
        self.literals = []
        self.functions = []
        for i in range(len(item)):
            if item[i] in ['1', '0']:
                self.length += 1
                self.literals.append(i)

    def getId(self):
        return self.id

    def addFunction(self, pos):
        if pos != -1:
            self.frequency += 1
        self.functions.append(pos)

    def getFrequency(self):
        return self.frequency

    def getPattern(self):
        return self.bitPattern

    def getSize(self):
        return self.length