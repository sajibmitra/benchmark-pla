from rpla import RPLA
from literal import Literal

class ExistingCalculation:
    def __init__(self, rpla, cost_calc=None):
        self.rpla = rpla
        self.functions = rpla.functions
        self.products = rpla.products
        self.finalProducts = []
        self.literals = []
        self.quantumCost = 0
        self.garbages = 0
        self.gates = 0
        self.delay = 0
        self.cost_calc = cost_calc

    def funProRearrange(self):
        mapping = list(range(len(self.products)))
        self.products.sort(key=lambda p: p.getFrequency())
        for i, product in enumerate(self.products):
            mapping[product.id] = i
        for function in self.functions:
            function.productsList = [mapping[pos] for pos in function.productsList]
        for i in range(len(self.functions) - 1, 0, -1):
            if self.functions[i - 1].getSize() == 1:
                self.functions[i], self.functions[i - 1] = self.functions[i - 1], self.functions[i]
                break

    def xorPlane(self):
        xorTDOT = 0
        totalXOROperation = 0
        self.funProRearrange()
        self.resetFlagOfProduct()
        for function in reversed(self.functions):
            totalXOROperation += function.getSize() - 1
            if function.getSize() == 1:
                if not self.products[function.productsList[0]].flag:
                    xorTDOT += 1
                    self.products[function.productsList[0]].flag = True
            else:
                flag = 0
                for prod_idx in function.productsList:
                    if not self.products[prod_idx].flag:
                        if flag == 0:
                            xorTDOT += 1
                            flag = 1
                        self.products[prod_idx].flag = True
        self.resetFlagOfProduct()
        count = 0
        for function in reversed(self.functions):
            function.productsList.sort(reverse=True)
            if function.productsList:
                count = self.products[function.productsList[0]].delayCountXOR
            else:
                count = 0
            flag = 0
            for j, prod_idx in enumerate(function.productsList):
                if not self.products[prod_idx].flag:
                    flag = 1
                    self.products[prod_idx].flag = True
                if self.products[prod_idx].delayCountXOR + 1 > count:
                    count = self.products[prod_idx].delayCountXOR + 1
                else:
                    count += 1
                if j == function.getSize() - 1 and flag == 1:
                    count -= 1
                self.products[prod_idx].delayCountXOR = count
        self.gates = totalXOROperation + len(self.functions) - xorTDOT
        self.garbages = len(self.products) - xorTDOT
        self.quantumCost = self.gates
        print("==========================================================")
        print("                Existing Calculation")
        print("==========================================================")
        print("      Rearranged FUNCTIONS & PRODUCTS ")
        print("==========================================================")
        self.showFunctions()
        self.showProducts()
        print("==========================================================")
        print("                     EXOR Plane")
        print("==========================================================")
        print(f"Total EXOR Operations : {totalXOROperation}")
        print(f"TDOT                  : {xorTDOT}")
        print(f"Feynman Gate          : {self.gates}")
        print(f"Garbage, GB           : {self.garbages}")
        print("==========================================================")

    def andPlane(self):
        andTDOT = 0
        totalANDOperation = 0
        constantProductExist = False
        self.initializeDoubleLiteral()
        for i in range(len(self.products) - 1, -1, -1):
            tempProduct = self.products[i]
            flag = False
            if tempProduct.getSize() > 0:
                for index in tempProduct.literals:
                    if not flag:
                        andTDOT += 1
                        self.literals[index].dotFlag = True
                    flag = True
                    self.literals[index].flag = True
                totalANDOperation += tempProduct.getSize() - 1
            else:
                constantProductExist = True
        for tempLiteral in self.literals:
            count = 0
            if tempLiteral.productsList:
                count = self.products[tempLiteral.productsList[0]].delayCountAND
            for j, prod_idx in enumerate(tempLiteral.productsList):
                if self.products[prod_idx].delayCountAND + 1 > count:
                    count = self.products[prod_idx].delayCountAND + 1
                else:
                    count += 1
                if j == len(tempLiteral.productsList) - 1 and tempLiteral.dotFlag:
                    count -= 1
                self.products[prod_idx].delayCountAND = count
        if constantProductExist:
            totalXOROperation = len(self.products) - andTDOT - 1
        else:
            totalXOROperation = len(self.products) - andTDOT
        totalXOROperation += len(self.literals) // 2
        totalGarbages = totalANDOperation + 2 * (len(self.literals) // 2) - andTDOT
        self.quantumCost += totalANDOperation * 5 + totalXOROperation
        self.delay = 0
        for product in self.products:
            if product.getSize() != 0:
                product.delayCountAND += 1
            self.delay = max(self.delay, product.delayCountAND + product.delayCountXOR)
        self.gates += totalANDOperation + totalXOROperation
        self.garbages += totalGarbages
        print("==========================================================")
        print("                    AND Plane")
        print("==========================================================")
        print(f"Total AND Operations: {totalANDOperation}")
        print(f"TDOT                : {andTDOT}")
        print(f"Total Toffoli Gates : {totalANDOperation}")
        print(f"Total Feynman Gates : {totalXOROperation}")
        print(f"Garbage, GB         : {totalGarbages}\n")
        print("==========================================================")
        print("                  Delay ")
        print("==========================================================")

    def showFinalResult(self):
        print("==========================================================")
        print(f"           Final Calculation of {self.rpla.esopFileName}")
        print("==========================================================")
        if self.cost_calc is not None:
            print(f"Total Gates   : {self.gates}({self.cost_calc.gates})")
            print(f"Total Garbages: {self.garbages}({self.cost_calc.garbages})")
            print(f"Total Delay   : {self.delay}({self.cost_calc.delay})")
            print(f"Total Q. Cost : {self.quantumCost}({self.cost_calc.quantumCost})")
        else:
            print(f"Total Gates   : {self.gates}")
            print(f"Total Garbages: {self.garbages}")
            print(f"Total Delay   : {self.delay}")
            print(f"Total Q. Cost : {self.quantumCost}")

    def initializeDoubleLiteral(self):
        self.literals = []
        for i in range(len(self.products)):
            self.products[i].literals.clear()
            item = self.products[i].bitPattern
            for j in range(2 * RPLA.totalLiterals):
                if i == 0:
                    self.literals.append(Literal(j))
                if item[j // 2] == '1' and j % 2 == 0:
                    self.products[i].literals.append(j)
                    self.literals[j].addProduct(i)
                elif item[j // 2] == '0' and j % 2 == 1:
                    self.products[i].literals.append(j)
                    self.literals[j].addProduct(i)

    def resetFlagOfProduct(self):
        for product in self.products:
            product.flag = False
            product.delayCountAND = 0
            product.delayCountXOR = 0

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
