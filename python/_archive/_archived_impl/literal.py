class Literal:
    def __init__(self, id):
        self.id = id
        self.frequency = 0
        self.dotFlag = False
        self.flag = False
        self.productsList = []

    def addProduct(self, productId):
        self.frequency += 1
        self.productsList.append(productId)

    def getSize(self):
        return self.frequency