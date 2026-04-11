/*********************************************************
 *          Author : Sajib Kumar Mitra
 *         Position: M.Sc.(1st Semester)/2008-09
 *       Department: Computer Science and Engineering
 *        Institute: University of Dhaka
 *            Email: sajibmitra.csedu@yahoo.com
 *            Phone: +8801710283239
 *********************************************************/
package benchmarkpla;
import java.util.ArrayList;
import java.util.Collections;
public class CostCalculation {
    public static int gates;               //Total number of gates
    public static int garbages;            //Total number of garbages
    public static int delay;               //delay calculation
    public static int quantumCost;         //Quantum Cost Calculation
    public ArrayList<Function> functions;   //store functions
    public ArrayList<Product> products;     //store products
//finalProducts store the ordered series of Products
    public ArrayList<Product> finalProducts;
    public ArrayList<Literal> literals;
    public Function tempFunction;
    public Product  tempProduct;
    public Literal  tempLiteral;
//xorTDOT for XOR plane and andTDOT for AND plane
    private int xorTDOT;
    private int andTDOT;
    private Boolean constantProductExist;
//this constructor initializes the functions and products by using initial status
    public CostCalculation(){
        functions=RPLA.functions;
        products=RPLA.products;
        finalProducts=new ArrayList<Product>();
        literals=new ArrayList<Literal>();
        quantumCost=0;
        garbages=0;
        gates=0;
        delay=0;
    }
//XOR Plane calculates the total number of gates and garbages
    public void xorPlane(){
        xorTDOT=0;
        int totalXOROperation=0;
        sortFunctions();        
        resetFlagOfProduct();
        for(int i=0;i<RPLA.totalOutputs;i++){
            tempFunction=functions.get(i);
            totalXOROperation+=tempFunction.getSize()-1;
            if(tempFunction.getSize()==1){
                if(!products.get(tempFunction.productsList.get(0)).flag){
                    xorTDOT++; products.get(tempFunction.productsList.get(0)).flag=true;
                    finalProducts.add(products.get(tempFunction.productsList.get(0)));
                    tempFunction.productsList.set(0,finalProducts.size()-1);
                }
                else {/* Product is exist*/}
            }
            else{
                int flag=0;
                for(int j=0;j<tempFunction.getSize();j++){
                    if(!products.get(tempFunction.productsList.get(j)).flag){
                       if(flag==0){flag=1;xorTDOT++;} else{}
                           products.get(tempFunction.productsList.get(j)).flag=true;
                           finalProducts.add(products.get(tempFunction.productsList.get(j)));
                           tempFunction.productsList.set(j,finalProducts.size()-1);
                    }
                    else{
                           tempFunction.productsList.set(j,getUpdatedIdOfPro(tempFunction.productsList.get(j)));
                    }
                }
            }
            functions.set(i, tempFunction);            
        }
        products=finalProducts;
        sortProductListOfFunc();
        resetFlagOfProduct();       
        int count=0;
        for(int i=0;i<RPLA.totalOutputs;i++){
            tempFunction=functions.get(i);
            if(tempFunction.productsList.size()!=0)
            count=products.get(tempFunction.productsList.get(0)).delayCountXOR;
            else
            count=0;
            int flag=0;
            for(int j=0;j<tempFunction.getSize();j++){                
                if(!products.get(tempFunction.productsList.get(j)).flag){
                    flag=1; products.get(tempFunction.productsList.get(j)).flag=true;
                }                
                if(products.get(tempFunction.productsList.get(j)).delayCountXOR+1>count)
                    count=products.get(tempFunction.productsList.get(j)).delayCountXOR+1;
                else
                    count++;
                if(j==tempFunction.getSize()-1&&flag==1){
                    //System.out.println("ok in");
                    count--;
                }
                products.get(tempFunction.productsList.get(j)).delayCountXOR=count;
             }
        }
        gates=totalXOROperation+RPLA.totalOutputs-xorTDOT;
        garbages=RPLA.totalProducts-xorTDOT;
        quantumCost=gates;
//Remove the following command to show detail..
        
      System.out.println("==========================================================");
        System.out.println("                Proposed Design");
        System.out.println("==========================================================");
        System.out.println("                Sorted FUNCTIONS ");
                            showFunctions();
        System.out.println("==========================================================");
        System.out.println("               Rearranged PRODUCTS ");
                            showProducts();
        System.out.println("==========================================================");
        System.out.println("             Calculation of EX-OR Plane");
        System.out.println("==========================================================");
        System.out.println("Total EXOR Operations : "+totalXOROperation);
        System.out.println("TDOT                  : "+xorTDOT);
        System.out.println("Feynman Gate          : "+gates);
        System.out.println("Garbage, GB           : "+garbages);
        System.out.println("==========================================================");
       
    }
//AND Plane calculates the total number of gates and garbages
    public void andPlane(){
        Boolean flag;
        andTDOT=0;
        int totalANDOperation=0;
        int totalXOROperation=0;
        int totalGarbages =0;
        constantProductExist=Boolean.FALSE;
        initializeLiteral();
        
        for(int i=0;i<RPLA.totalProducts;i++){
            tempProduct=products.get(i);
            flag=false;
            if(tempProduct.getSize()>0){
                for(int j=0;j<tempProduct.getSize();j++){
                    int index =tempProduct.literals.get(j);
                    if(!flag&&!literals.get(index).flag&&tempProduct.bitPattern.charAt(index)=='1'){andTDOT++;literals.get(index).dotFlag=Boolean.TRUE;}
                    flag=true;
                    literals.get(index).flag=true;
                }
                totalANDOperation+=tempProduct.getSize()-1;
            }
            else
              constantProductExist=Boolean.TRUE;           
        }
        int count=0;
        for(int i=0;i<RPLA.totalLiterals;i++){
            tempLiteral=literals.get(i);
            Collections.sort(tempLiteral.productsList, Collections.reverseOrder());
            count=products.get(tempLiteral.productsList.get(0)).delayCountAND;
            //System.out.print("Func: "+ functions.get(i).id);
            for(int j=0;j<tempLiteral.getSize();j++){
                if(products.get(tempLiteral.productsList.get(j)).delayCountAND+1>count)
                    count=products.get(tempLiteral.productsList.get(j)).delayCountAND+1;
                else
                    count++;
                if(j==(tempLiteral.getSize()-1)&& tempLiteral.dotFlag)
                    count--;
                else{}
               products.get(tempLiteral.productsList.get(j)).delayCountAND=count;
             }
        }
//comments the following things if U want to detail after removing the comments mark in follows
    /*    if(constantProductExist)
            totalXOROperation=RPLA.totalProducts-andTDOT-1;
        else
            totalXOROperation=RPLA.totalProducts-andTDOT;

            totalGarbages=totalANDOperation+RPLA.totalLiterals-andTDOT;
        quantumCost+=totalANDOperation*4+totalXOROperation;
        delay=0;
        for(int j=0;j<RPLA.totalProducts;j++){
                if(delay<(products.get(j).delayCountAND+products.get(j).delayCountXOR)){
                    delay=products.get(j).delayCountAND+products.get(j).delayCountXOR;
                }
            }
        gates+=totalANDOperation+totalXOROperation;
        garbages+=totalGarbages;*/
//If U want to show detail U should delete the code in above from "If(constantProductExist)"
        System.out.println("==========================================================");
        System.out.println("             Calculation of AND Plane");
        System.out.println("==========================================================");
        System.out.println("Total AND Operations: " +totalANDOperation);
        System.out.println("TDOT                : "+andTDOT);
        System.out.println("Total MUX Gates (MG): "+totalANDOperation);
        if(constantProductExist)
            totalXOROperation=RPLA.totalProducts-andTDOT-1;
        else
            totalXOROperation=RPLA.totalProducts-andTDOT;
        
        System.out.println("Total Feynman Gate  : "+totalXOROperation);
            totalGarbages=totalANDOperation+RPLA.totalLiterals-andTDOT;
        System.out.println("Garbage, GB         : "+totalGarbages);
        System.out.println("==========================================================");
        System.out.println("                  Delay ");
        System.out.println("==========================================================");
        System.out.println("    Delay (AND) |  Delay (EXOR)   = Total Delay");
        System.out.println("==========================================================");
        quantumCost+=totalANDOperation*4+totalXOROperation;
        delay=0;
        for(int j=0;j<RPLA.totalProducts;j++){
                System.out.println("P"+ products.get(j).id+" :     "+products.get(j).delayCountAND+"              "+products.get(j).delayCountXOR +"            "+ (products.get(j).delayCountAND+products.get(j).delayCountXOR));
                if(delay<(products.get(j).delayCountAND+products.get(j).delayCountXOR)){
                    delay=products.get(j).delayCountAND+products.get(j).delayCountXOR;
                }
            }
        gates+=totalANDOperation+totalXOROperation;
        garbages+=totalGarbages;
    }
//showFinalResult() shows the final calculation
    public void showFinalResult(){
      System.out.println("==========================================================");
      System.out.println("       Final Calculation of "+RPLA.esopFileName);
      System.out.println("==========================================================");
      System.out.println("Total Gates: "+gates);
      System.out.println("Total Garbages: "+garbages);
      System.out.println("Total Delay: "+delay);
      System.out.println("Total Q. Cost: "+quantumCost);
      System.out.println("==========================================================");
    }
//reinitialize literal for garbages and gate calculation
    public void initializeLiteral(){
        for(int i=0;i<RPLA.totalProducts;i++){
            tempProduct=products.get(i);
            String item=tempProduct.bitPattern;
         for(int j=0;j<RPLA.totalLiterals;j++){
            if(i==0) literals.add(new Literal(j));
            else {}            
            if(item.charAt(j)=='1'|| item.charAt(j)=='0') {
              literals.get(j).addProduct(i);
            }
            else{}
         }
       }
    }
    public void resetFlagOfProduct(){
       for(int j=0;j<RPLA.totalProducts;j++){
                products.get(j).flag=false;
                products.get(j).delayCountAND=0;
                products.get(j).delayCountXOR=0;
            }
    }
    public int getUpdatedIdOfPro(int previousId){
        int i;
        for(i=0;i<finalProducts.size();i++){
            if(finalProducts.get(i).id==previousId){
             break;
            }
        }
        return i;
    }
    public void sortFunctions(){
     Function tempFunc;
     for(int i=0;i<functions.size()-1;i++){
         for(int j=i+1;j<functions.size();j++){
             if(functions.get(i).getSize()>functions.get(j).getSize()){
                tempFunc=functions.get(i);
                functions.set(i,functions.get(j));
                functions.set(j,tempFunc);
             }
             else{}
         }
      }
    }
    public void sortProductListOfFunc(){
        for(int i=0;i<RPLA.totalOutputs;i++){                          
                 Collections.sort(functions.get(i).productsList);
    }
    }
    public void showProducts(){
        System.out.println("----------------------------------------------------------");
            for(int i=0;i<RPLA.totalProducts;i++){
                         System.out.print ("Product ["+products.get(i).id+"]: ");
                         for(int j=0;j<products.get(i).functions.size();j++){
                                int pos=products.get(i).functions.get(j);
                             if(pos>=0){
                                System.out.print("f"+j+"("+pos+ ") ");
                             }
                         }                         
                         System.out.println();
                      }
       System.out.println("----------------------------------------------------------");
    }
    public void showFunctions(){
        System.out.println("----------------------------------------------------------");
        for(int i=0;i<RPLA.totalOutputs;i++){
                          System.out.print("Function ["+functions.get(i).id+"]: ");                          
                          for(int j=0;j<functions.get(i).productsList.size();j++){
                             System.out.print("P"+products.get(functions.get(i).productsList.get(j)).id);
                             if(j!=functions.get(i).productsList.size()-1)
                             System.out.print(",");
                          }
                          System.out.println();
                      }
        System.out.println("----------------------------------------------------------");
    }
}
