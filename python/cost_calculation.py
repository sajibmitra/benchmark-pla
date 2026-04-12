from rpla import RPLA
from literal import Literal

class CostCalculation:
    def __init__(self, rpla):
        self.functions = rpla.functions
        self.products = rpla.products
        self.finalProducts = []
        self.literals = []
        self.quantumCost = 0
        self.garbages = 0
        self.gates = 0
        self.delay = 0
        self.xorTDOT = 0

    def xorPlane(self, plane_banner="Proposed Design"):
        self.xorTDOT = 0
        totalXOROperation = 0
        self.sortFunctions()
        self.resetFlagOfProduct()
        for i in range(len(self.functions)):
            tempFunction = self.functions[i]
            totalXOROperation += tempFunction.getSize() - 1
            if tempFunction.getSize() == 1:
                if not self.products[tempFunction.productsList[0]].flag:
                    self.xorTDOT += 1
                    self.products[tempFunction.productsList[0]].flag = True
                    self.finalProducts.append(self.products[tempFunction.productsList[0]])
                    tempFunction.productsList[0] = len(self.finalProducts) - 1
            else:
                flag = 0
                for j in range(tempFunction.getSize()):
                    product_index = tempFunction.productsList[j]
                    if not self.products[product_index].flag:
                        if flag == 0:
                            flag = 1
                            self.xorTDOT += 1
                        self.products[product_index].flag = True
                        self.finalProducts.append(self.products[product_index])
                        tempFunction.productsList[j] = len(self.finalProducts) - 1
                    else:
                        tempFunction.productsList[j] = self.getUpdatedIdOfPro(tempFunction.productsList[j])
            self.functions[i] = tempFunction
        self.products = self.finalProducts
        self.sortProductListOfFunc()
        self.resetFlagOfProduct()
        for i in range(len(self.functions)):
            tempFunction = self.functions[i]
            count = 0
            if tempFunction.productsList:
                count = self.products[tempFunction.productsList[0]].delayCountXOR
            flag = 0
            for j in range(tempFunction.getSize()):
                prod_index = tempFunction.productsList[j]
                if not self.products[prod_index].flag:
                    flag = 1
                    self.products[prod_index].flag = True
                if self.products[prod_index].delayCountXOR + 1 > count:
                    count = self.products[prod_index].delayCountXOR + 1
                else:
                    count += 1
                if j == tempFunction.getSize() - 1 and flag == 1:
                    count -= 1
                self.products[prod_index].delayCountXOR = count
        self.gates = totalXOROperation + len(self.functions) - self.xorTDOT
        self.garbages = len(self.products) - self.xorTDOT
        self.quantumCost = self.gates
        print("==========================================================")
        print(f"                {plane_banner}")
        print("==========================================================")
        print("                Sorted FUNCTIONS ")
        self.showFunctions()
        print("==========================================================")
        print("               Rearranged PRODUCTS ")
        self.showProducts()
        print("==========================================================")
        print("             Calculation of EX-OR Plane")
        print("==========================================================")
        print(f"Total EXOR Operations : {totalXOROperation}")
        print(f"TDOT                  : {self.xorTDOT}")
        print(f"Feynman Gate          : {self.gates}")
        print(f"Garbage, GB           : {self.garbages}")
        print("==========================================================")

    def andPlane(self):
        andTDOT = 0
        totalANDOperation = 0
        totalGarbages = 0
        constantProductExist = False
        self.initializeLiteral()
        for i in range(len(self.products)):
            tempProduct = self.products[i]
            flag = False
            if tempProduct.getSize() > 0:
                for j in tempProduct.literals:
                    index = j
                    if not flag and not self.literals[index].flag and tempProduct.bitPattern[index] == '1':
                        andTDOT += 1
                        self.literals[index].dotFlag = True
                    flag = True
                    self.literals[index].flag = True
                totalANDOperation += tempProduct.getSize() - 1
            else:
                constantProductExist = True
        for i in range(len(self.literals)):
            tempLiteral = self.literals[i]
            tempLiteral.productsList.sort(reverse=True)
            count = 0
            if tempLiteral.productsList:
                count = self.products[tempLiteral.productsList[0]].delayCountAND
            for j in tempLiteral.productsList:
                if self.products[j].delayCountAND + 1 > count:
                    count = self.products[j].delayCountAND + 1
                else:
                    count += 1
                if j == tempLiteral.productsList[-1] and tempLiteral.dotFlag:
                    count -= 1
                self.products[j].delayCountAND = count
        if constantProductExist:
            totalXOROperation = len(self.products) - andTDOT - 1
        else:
            totalXOROperation = len(self.products) - andTDOT
        totalGarbages = totalANDOperation + len(self.literals) - andTDOT
        self.quantumCost += totalANDOperation * 4 + totalXOROperation
        self.delay = 0
        for j in range(len(self.products)):
            self.delay = max(self.delay, self.products[j].delayCountAND + self.products[j].delayCountXOR)
        self.gates += totalANDOperation + totalXOROperation
        self.garbages += totalGarbages
        print("==========================================================")
        print("             Calculation of AND Plane")
        print("==========================================================")
        print(f"Total AND Operations: {totalANDOperation}")
        print(f"TDOT                : {andTDOT}")
        print(f"Total MUX Gates (MG): {totalANDOperation}")
        print(f"Total Feynman Gate  : {totalXOROperation}")
        print(f"Garbage, GB         : {totalGarbages}")
        print("==========================================================")
        print("                  Delay ")
        print("==========================================================")
        print("    Delay (AND) |  Delay (EXOR)   = Total Delay")
        print("==========================================================")

    def initializeLiteral(self):
        self.literals = []
        for i in range(len(self.products)):
            tempProduct = self.products[i]
            item = tempProduct.bitPattern
            for j in range(len(item)):
                if i == 0:
                    self.literals.append(Literal(j))
                if item[j] in ['1', '0']:
                    self.literals[j].addProduct(i)

    def resetFlagOfProduct(self):
        for product in self.products:
            product.flag = False
            product.delayCountAND = 0
            product.delayCountXOR = 0

    def getUpdatedIdOfPro(self, product_index):
        """Map current products-list index to index in finalProducts via stable Product.id."""
        pid = self.products[product_index].id
        for i, prod in enumerate(self.finalProducts):
            if prod.id == pid:
                return i
        return 0

    def sortFunctions(self):
        self.functions.sort(key=lambda f: f.getSize())

    def sortProductListOfFunc(self):
        for i in range(len(self.functions)):
            self.functions[i].productsList.sort()

    def showProducts(self):
        print("----------------------------------------------------------")
        for product in self.products:
            line = f"Product [{product.id}]: "
            line += ",".join(f"f{j}({pos})" for j, pos in enumerate(product.functions) if pos >= 0)
            print(line)
        print("----------------------------------------------------------")

    def showFunctions(self):
        print("----------------------------------------------------------")
        for function in self.functions:
            line = f"Function [{function.id}]: "
            line += ",".join(f"P{pos}" for pos in function.productsList)
            print(line)
        print("----------------------------------------------------------")