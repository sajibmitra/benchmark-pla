/*********************************************************
 *          Author : Sajib Kumar Mitra
 *         Position: M.Sc.(1st Semester)/2008-09
 *       Department: Computer Science and Engineering
 *        Institute: University of Dhaka
 *            Email: sajibmitra.csedu@yahoo.com
 *            Phone: +8801710283239
 *********************************************************/
package benchmarkpla;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Scanner;
import java.util.StringTokenizer;
public class RPLA {
    
    public static short  totalProducts;
    public static short  totalLiterals;
    public static short  totalOutputs;    
    public static int    selectedMenu;
    public static String esopFileName;
//Preserves the states of all functions
    public static ArrayList<Function> functions;
    public static ArrayList<Product>  products;
    public static ArrayList<Product>  patternsOfProduct;
    public static Scanner io;
    public static long time;
    public static void main(String[] args) {
        RPLA rplaObj=new RPLA();
        while(true){    
               io=new Scanner(System.in);
               System.out.println("(1) Calculation of Cost of an ESOP PLA");
               System.out.println("(2) Convert SOP Expression into PLA (.pla)");
               System.out.println("(3) Convert ESOP Expression into ESOP PLA (.esop)");
               System.out.println("(4) Exit");
               System.out.print("Please Enter a number between 1 to 4 : ");
               String select=io.nextLine();
               functions= new ArrayList<Function>();
               products = new ArrayList<Product>();
               patternsOfProduct= new ArrayList<Product>();
               totalLiterals=0;
               totalProducts=0;
               totalOutputs=0;
           if(select.equalsIgnoreCase("1")==true){
                   selectedMenu=1;
                   System.out.print("\nEnter File (.esop) Name:");
                   rplaObj.readDataFromESOPFile(io.nextLine());
           }
           else if(select.equalsIgnoreCase("2")==true){
                   selectedMenu=2;
                   System.out.print("\nEnter File Name:");
                   rplaObj.readDataManually(io.nextLine());
                   
           }
           else if(select.equalsIgnoreCase("3")==true){
                   selectedMenu=3;
                   System.out.print("\nEnter File Name:");
                   rplaObj.readDataManually(io.nextLine());                   
           }
           else if(select.equalsIgnoreCase("4")==true)
               System.exit(0);
        }
    }
    public void readDataFromESOPFile(String fileName){
//just add extension after given function name
        esopFileName=fileName+".esop";
        File fileObj = new File(esopFileName);
        try{
            Scanner fileScanner=new Scanner(fileObj);
            while(fileScanner.hasNextLine()){
            String line=fileScanner.nextLine();
            inputFormat(line);
            }
        } catch(FileNotFoundException e){
            System.out.println("File Not Found...");
        }
    }
//following function will read data from given multi-outputs functions and 
//will save it into .pla or .esop file respect to user demand    
    public void readDataManually(String fileName){
        File fileObj = new File(fileName);
        try{
            Scanner fileScanner=new Scanner(fileObj);
            StringTokenizer stringTokenizer;
            totalProducts=0;
            int functionCounter=0;
            System.out.println("==========================================================");
                System.out.println("                  "+ fileName);
                System.out.println("----------------------------------------------------------");
            while(fileScanner.hasNextLine()){
                String line=fileScanner.nextLine();
                System.out.println(line);
                stringTokenizer=new StringTokenizer(line);
                String token=stringTokenizer.nextToken();
                  if(token.equalsIgnoreCase(".i"))
                      totalLiterals=(short) Short.parseShort(stringTokenizer.nextToken());
                  else if(token.equalsIgnoreCase(".o"))
                      totalOutputs=(short) Short.parseShort(stringTokenizer.nextToken());
                  else if(token.equalsIgnoreCase(".e")){
                      System.out.println("==========================================================");
                      PrintWriter pw = null;
                      try {
                          if(selectedMenu==2)
                            fileName=fileName+".pla";
                          else
                            fileName=fileName+".esop";

                          pw = new PrintWriter(new FileWriter(fileName));
                            pw.println(".i "+totalLiterals);
                            pw.println(".o "+totalOutputs);
                            pw.println(".p "+totalProducts);
                          for(int i=0;i<patternsOfProduct.size();i++){
                            pw.println(patternsOfProduct.get(i).bitPattern+" "+getPatternOfFunction(i));
                          }
                          pw.print(".e");
                          pw.flush();
                          pw.close();
                          fileObj = new File(fileName);
                          fileScanner=new Scanner(fileObj);
                           System.out.println("==========================================================");
                                System.out.println("                  "+ fileName);
                                System.out.println("----------------------------------------------------------");
                                while(fileScanner.hasNextLine()){
                                    line=fileScanner.nextLine();
                                    System.out.println(line);
                                }
                         System.out.println("==========================================================");
                        }
                        catch (IOException e) {
                          e.printStackTrace();
                        }
                        finally {                          
                          if (pw != null){
                            pw.close();                           
                          }
                        }
                  }
                  else{
                    StringTokenizer stringTokenizer1=new StringTokenizer(line);
                    while(stringTokenizer1.hasMoreTokens()){
                        String data;
//specify the selection of input by using selectedMenu variables
                        if(selectedMenu==2)
                        data=stringTokenizer1.nextToken("+");
                        else
                        data=stringTokenizer1.nextToken("^");

                        Boolean flag=Boolean.TRUE;
                        for(int i=0;i<patternsOfProduct.size();i++){
                            if(patternsOfProduct.get(i).bitPattern.equals(getPatternOfProduct(data))){
                                flag=Boolean.FALSE;
                                patternsOfProduct.get(i).addFunction(functionCounter);                                
                            }
                        }
                        if(flag){
                            patternsOfProduct.add(new Product(totalProducts,getPatternOfProduct(data)));
                            patternsOfProduct.get(totalProducts).addFunction(functionCounter);
                            totalProducts++;
                        } 
                    }
                    functionCounter++;
                }
                
            }
        
        } catch(FileNotFoundException e){
            System.out.println("File Not Found...");
        }
    }
//Product pattern analyzer to write pattern
    public String getPatternOfProduct(String data){
        String pattern="";        
        int j;
        for(j=0;j<totalLiterals;j++){
            pattern=pattern+"-";
        }
        StringBuffer stringBuffer=new StringBuffer(pattern);
        for(int i=0;i<data.length();i++){
            int p = (int)data.charAt(i);
            if(p>=65&&p<91) stringBuffer.setCharAt(p-65,'0');
            else if(p>=97&&p<123) stringBuffer.setCharAt(p-97,'1');
            else{}            
        }        
    return stringBuffer.toString();
    }
//Functions pattern analyzer to write pattern
    public String getPatternOfFunction(int productIndex){
        String pattern="";
        int j;
        for(j=0;j<totalOutputs;j++){
            pattern=pattern+"0";
        }
        StringBuffer stringBuffer=new StringBuffer(pattern);
        Product baseProduct=patternsOfProduct.get(productIndex);
        for(int i=0;i<baseProduct.functions.size();i++){
            stringBuffer.setCharAt(baseProduct.functions.get(i),'1');
        }
    return stringBuffer.toString();
    }
    public int inputFormat(String data){
        StringTokenizer stringTokenizer=new StringTokenizer(data);
        while(stringTokenizer.hasMoreTokens()){
            //System.out.println(" Token : "+count+" : "+stringTokenizer.nextToken());
            String token=stringTokenizer.nextToken();
                  if(token.equalsIgnoreCase(".i"))
                      totalLiterals=(short) Short.parseShort(stringTokenizer.nextToken());
                  else if(token.equalsIgnoreCase(".o"))
                      totalOutputs=(short) Short.parseShort(stringTokenizer.nextToken());
                  else if(token.equalsIgnoreCase(".p"))
                      totalProducts=(short) Short.parseShort(stringTokenizer.nextToken());
                  else if(token.equalsIgnoreCase(".e")){
                              
                      CostCalculation costCalculation=new CostCalculation();                      
                      /*System.out.println("==========================================================");
                      System.out.println("                    PRODUCTS ");
                      costCalculation.showProducts();
                      System.out.println("                    FUNCTIONS ");
                      costCalculation.showFunctions();*/
                     // time=System.nanoTime();
                      costCalculation.xorPlane();                      
                      costCalculation.andPlane();                     
                      //time=System.nanoTime()-time;
                      //System.out.println("Proposed Design takes " + (float)time/1000000 + " nanoseconds");
                     // costCalculation.showFinalResult();

                      ExistingCalculation existingCalculation=new ExistingCalculation();
                      //time=System.nanoTime();
                      existingCalculation.xorPlane();
                      existingCalculation.andPlane();                      
                      //time=System.nanoTime()-time;
                      //System.out.println("Existing Design takes " + (float)time/1000000 + " nanoseconds");
                      existingCalculation.showFinalResult();



                      time=System.nanoTime();
                      for(int i=0;i<totalOutputs-1;i++)
                          for(int j=i+1;j<totalOutputs;j++){}
                      for(int i=0;i<totalOutputs;i++)
                          for(int j=0;j<functions.get(i).getSize();j++){}
                       for(int i=0;i<totalProducts;i++)
                          for(int j=0;j<products.get(i).getSize();j++){}
                        time=System.nanoTime()-time;
                      System.out.println("Proposed Design takes " + (float)time/10000 + " nanoseconds");
                      
                        time=System.nanoTime();
                      for(int i=0;i<totalProducts-1;i++)
                          for(int j=i+1;j<totalProducts;j++){}
                      for(int i=0;i<totalProducts-1;i++)
                          for(int j=i+1;j<totalProducts;j++){}
                      for(int i=0;i<totalOutputs-1;i++)
                          for(int j=i+1;j<totalOutputs;j++){}

                      for(int i=0;i<totalProducts;i++)
                          for(int j=0;j<products.get(i).getSize();j++){}
                      for(int i=0;i<totalOutputs;i++)
                          for(int j=0;j<functions.get(i).getSize();j++){}
                        time=System.nanoTime()-time;
                      System.out.println("Existing Design takes " + (float)time/10000 + " nanoseconds");

                  }
                  else{
//add new product to product list
                       products.add(new Product(products.size(),token));                        
                        String temp=stringTokenizer.nextToken();
                        for(int i=0;i<totalOutputs;i++){                            
                            if(functions.size()<(i+1))
                                functions.add(new Function(i));
                            else {
                            }
                            if(temp.charAt(i)=='1'){
                                int posOfProcInFunc=functions.get(i).addProduct(products.size()-1);
                                products.get(products.size()-1).addFunction(posOfProcInFunc);
                            }
                            else{
                                products.get(products.size()-1).addFunction(-1);
                            }
                        }
                }
          }
    return 0;
    }    
}