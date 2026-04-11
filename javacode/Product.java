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
public class Product {
    public int id;              //product Id
    public String bitPattern;   //bit pattern of product
    public int frequency;       //total number of used functions
    public int delayCountAND;   //delay respect to AND plane
    public int delayCountXOR;   //delay respect to XOR plane
    public boolean flag;        //flag is used to compute delay
    public int length;          //length of total literal except don't care
//list of literal except don't care for a particular product
    public ArrayList<Integer> literals=new ArrayList<Integer>();
//list of the position of this products in another functions
    public ArrayList<Integer> functions=new ArrayList<Integer>();
//Initialization of the product
    public Product(int id, String item){
        this.id=id;
        bitPattern=item;
        flag=false;
        this.frequency=0;
        this.delayCountAND=0;
        this.delayCountXOR=0;
        this.length=0;
        for(int i=0;i<item.length();i++){
            if(item.charAt(i)=='1'|| item.charAt(i)=='0') {
              this.length++; literals.add(i);            
            }
        }
    }
//Return the id of product
    public int getId(){
        return this.id;
    }
//If any function add this Product then itself keeps the possition into the function
    public void addFunction(int pos){               
               if(pos!=-1)
                   this.frequency++;
               else{}
               functions.add(pos);
    }
//Return the Frequency
    public int getFrequency(){
        return this.frequency;
    }
//return the pattern of product
    public String getPattern(){
        return bitPattern;
    }
//return the lengh product string
    public int getSize(){
        return length;
    }
}