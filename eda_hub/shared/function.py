class Function:
    def __init__(self, funcId):
        self.id = funcId
        self.productDensity = 0
        self.productsList = []

    def addProduct(self, productId):
        self.productsList.append(productId)
        self.productDensity += 1
        return len(self.productsList) - 1

    def getData(self):
        return self.productsList

    def getSize(self):
        return self.productDensity