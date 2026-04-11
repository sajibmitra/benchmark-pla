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
public class Literal {
    public int id;          //Literal's id: 0, 1, 2, 3, ....
    public boolean flag;    //flag is used in various purpose
    public boolean dotFlag; //is that literal got a dot at AND plane
    public int frequency;   //Total used in AND plane
//Keeps the list of Product for delay calculation
    public ArrayList<Integer> productsList=new ArrayList<Integer>();
//Initialization of Literal
    public Literal(int id){
        this.id=id;
        this.frequency=0;
        this.dotFlag=Boolean.FALSE;
        this.flag=Boolean.FALSE;
    }
//Adds the product ID at product liest and increases the frequency
    public void addProduct(int productId){
        this.frequency++;
        productsList.add(productId);
    }
//return the frequency of a literals
    public int getSize(){
        return frequency;
    }
}
