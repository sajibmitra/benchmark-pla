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
public class ExistingCalculation {

    private static int gates;               //Total number of gates
    private static int garbages;            //Total number of garbages
    private static int delay;               //delay calculation
    private static int quantumCost;         //Quantum Cost Calculation
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
    public ExistingCalculation(){
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
    public void funProRearrange(){
        ArrayList <Integer> mapping=new ArrayList<Integer>();
        for(int i=0;i<RPLA.totalProducts;i++){
            mapping.add(i);
        }
        for(int i=0;i<RPLA.totalProducts-1;i++)
            for(int j=i+1;j<RPLA.totalProducts;j++){
                if(products.get(i).getFrequency()>products.get(j).getFrequency()){
                     tempProduct=products.get(i);
                     products.set(i, products.get(j));
                     products.set(j, tempProduct);                                          
                }
            }
        for(int i=0;i<RPLA.totalProducts;i++){
            mapping.set(products.get(i).id,i);
        }        
        for(int i=0; i<RPLA.totalOutputs;i++){
                tempFunction=functions.get(i);
                for(int j=0;j<tempFunction.getSize();j++){
                    tempFunction.productsList.set(j,mapping.get(tempFunction.productsList.get(j)));
                }
        }
  //      showFunctions();
        for(int i=RPLA.totalOutputs-1;i>=1;i--)
            for(int j=i-1;j>=0;j--)
                if(functions.get(j).getSize()==1){
                    tempFunction=functions.get(i);
                    functions.set(i, functions.get(j));
                    functions.set(j, tempFunction);
                    break;
                }
        }
    public void xorPlane(){
        xorTDOT=0;
        int totalXOROperation=0;
        funProRearrange();        
        resetFlagOfProduct();
        for(int i=RPLA.totalOutputs-1;i>=0;i--){
            tempFunction=functions.get(i);
             totalXOROperation+=tempFunction.getSize()-1;
            if(tempFunction.getSize()==1){
                if(!products.get(tempFunction.productsList.get(0)).flag){
                    xorTDOT++; products.get(tempFunction.productsList.get(0)).flag=true;
                }
                else { }
            }
            else{
                int flag=0;
                for(int j=0;j<tempFunction.getSize();j++){
                    if(!products.get(tempFunction.productsList.get(j)).flag){
                       if(flag==0){flag=1;xorTDOT++;} else{}
                           products.get(tempFunction.productsList.get(j)).flag=true;
                    }
                    else{ }
                }
            }
        }
        resetFlagOfProduct();
        int count=0;
        for(int i=RPLA.totalOutputs-1;i>=0;i--){
            tempFunction=functions.get(i);
            Collections.sort(tempFunction.productsList,Collections.reverseOrder());
            if(tempFunction.productsList.size()!=0)
                count=products.get(tempFunction.productsList.get(0)).delayCountXOR;
            else
                count=0;
            int flag=0;
            for(int j=0;j<tempFunction.getSize();j++){
                if(!products.get(tempFunction.productsList.get(j)).flag){ //If any product has not used yet
                    flag=1; products.get(tempFunction.productsList.get(j)).flag=true;
                }
                if(products.get(tempFunction.productsList.get(j)).delayCountXOR+1>count)
                    count=products.get(tempFunction.productsList.get(j)).delayCountXOR+1;
                else
                    count++;
                if(j==tempFunction.getSize()-1&&flag==1){
                       count--;
                }
                products.get(tempFunction.productsList.get(j)).delayCountXOR=count;
             }
        }
        gates=totalXOROperation+RPLA.totalOutputs-xorTDOT;
        garbages=RPLA.totalProducts-xorTDOT;
        quantumCost=gates;
//remove the comment symbol If U want to see detail..
        System.out.println("==========================================================");
        System.out.println("                Existing Calculation");
        System.out.println("==========================================================");
        System.out.println("      Rearranged FUNCTIONS & PRODUCTS ");
        System.out.println("==========================================================");
                      showFunctions();
                      showProducts();
        System.out.println("==========================================================");
        System.out.println("                     EXOR Plane");
        System.out.println("==========================================================");
        System.out.println("Total EXOR Operations : "+ totalXOROperation);
        System.out.println("TDOT                  : "+xorTDOT);
        System.out.println("Feynman Gate          : "+gates);
        System.out.println("Garbage, GB           : "+garbages);
        System.out.println("==========================================================");
    }
    public void andPlane(){
    Boolean flag;
        andTDOT=0;
        int totalANDOperation=0;
        int totalXOROperation=0;
        int totalGarbages =0;
        constantProductExist=Boolean.FALSE;
        initializeDoubleLiteral();
        for(int i=RPLA.totalProducts-1;i>=0;i--){
            tempProduct=products.get(i);
            flag=false;
            if(tempProduct.getSize()>0){
                for(int j=0;j<tempProduct.getSize();j++){
                    int index =tempProduct.literals.get(j);
                    if(!flag&&!literals.get(index).flag){
                        andTDOT++;
                        literals.get(index).dotFlag=Boolean.TRUE; // already used and has dot
                    }
                    flag=true;
                    literals.get(index).flag=true;  // already used but doesn't have dot
                }
                totalANDOperation+=tempProduct.getSize()-1;
            }
            else
              constantProductExist=Boolean.TRUE;
        }
        int count=0;
        for(int i=0;i<2*RPLA.totalLiterals;i++){
            tempLiteral=literals.get(i);

            if(tempLiteral.getSize()!=0)
            count=products.get(tempLiteral.productsList.get(0)).delayCountAND;
            else
            count=0;
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
        }/*
        if(constantProductExist)
            totalXOROperation=RPLA.totalProducts-andTDOT-1;
        else
            totalXOROperation=RPLA.totalProducts-andTDOT;
        totalXOROperation+=RPLA.totalLiterals;
        totalGarbages=totalANDOperation+2*RPLA.totalLiterals-andTDOT;
        quantumCost+=totalANDOperation*5+totalXOROperation;
        delay=0;
        for(int j=0;j<RPLA.totalProducts;j++){
            if(products.get(j).getSize()!=0)
                products.get(j).delayCountAND++;
                if(delay<(products.get(j).delayCountAND+products.get(j).delayCountXOR)){
                    delay=products.get(j).delayCountAND+products.get(j).delayCountXOR;
                }
            }
        gates+=totalANDOperation+totalXOROperation;
        garbages+=totalGarbages;*/
//Remove the code from "If(constantProductExist)" to here and remove the comments are shown in follows for detail view..

        System.out.println("==========================================================");
        System.out.println("                    AND Plane");
        System.out.println("==========================================================");
        System.out.println("Total AND Operations: " +totalANDOperation);
        System.out.println("TDOT                : "+andTDOT);
        System.out.println("Total Toffoli Gates : "+totalANDOperation);
        if(constantProductExist)
            totalXOROperation=RPLA.totalProducts-andTDOT-1;
        else
            totalXOROperation=RPLA.totalProducts-andTDOT;
        totalXOROperation+=RPLA.totalLiterals;
        System.out.println("Total Feynman Gates : "+totalXOROperation);
            totalGarbages=totalANDOperation+2*RPLA.totalLiterals-andTDOT;
        System.out.println("Garbage, GB         : "+totalGarbages+"\n");
        System.out.println("==========================================================");
        System.out.println("                  Delay ");
        System.out.println("==========================================================");
        System.out.println("    Delay (AND) |  Delay (EXOR)   = Total Delay");
        System.out.println("==========================================================");
        quantumCost+=totalANDOperation*5+totalXOROperation;
        delay=0;
        for(int j=0;j<RPLA.totalProducts;j++){
            if(products.get(j).getSize()!=0)
            products.get(j).delayCountAND++;
                System.out.println("P"+ products.get(j).id+" :     "+products.get(j).delayCountAND+"              "+products.get(j).delayCountXOR +"            "+ (products.get(j).delayCountAND+products.get(j).delayCountXOR));
                if(delay<(products.get(j).delayCountAND+products.get(j).delayCountXOR)){
                    delay=products.get(j).delayCountAND+products.get(j).delayCountXOR;
                }
            }
        gates+=totalANDOperation+totalXOROperation;
        garbages+=totalGarbages;
    }
    public void showFinalResult(){
      System.out.println("==========================================================");
      System.out.println("           Final Calculation of "+ RPLA.esopFileName);
      System.out.println("==========================================================");
      System.out.println("Total Gates   : "+gates +"("+CostCalculation.gates+")");
      System.out.println("Total Garbages: "+garbages+"("+CostCalculation.garbages+")");
      System.out.println("Total Delay   : "+delay+"("+CostCalculation.delay+")");
      System.out.println("Total Q. Cost : "+quantumCost+"("+CostCalculation.quantumCost+")");
      System.out.println("==========================================================");
    }
    public void initializeDoubleLiteral(){
        for(int i=0; i<RPLA.totalProducts;i++){
            products.get(i).literals.clear();
            String item=products.get(i).bitPattern;
         for(int j=0;j<2*RPLA.totalLiterals;j++){
            if(i==0) literals.add(new Literal(j));
            else {}
            if(item.charAt(j/2)=='1'&&(j%2==0)){
              products.get(i).literals.add(j);
              literals.get(j).addProduct(i);
            }
            else if(item.charAt(j/2)=='0'&&(j%2==1)){
                products.get(i).literals.add(j);
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
