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
public class Function {
    public int id;              //ID of a function
    public int productDensity;  //total number of products
//list of used product to build this function
    public ArrayList<Integer> productsList= new ArrayList<Integer>();
//Initialization of a function
    public Function(int funcId){
        id=funcId;
        productDensity=0;
    }
//Add product to function
    public int addProduct(int productId){
        productsList.add(productId);
        productDensity++;
//Return the position of this product in this function
        return productsList.size()-1;
    }
//return the overall function data
    public ArrayList<Integer> getData(){
         return productsList;
    }
//Total number of product to build function
    public int getSize(){
        return productDensity;
    }    
}