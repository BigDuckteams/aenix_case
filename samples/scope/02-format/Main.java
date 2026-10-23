import java.util.Formatter;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int count = in.nextInt();
        double price = in.nextDouble();
        String item = in.next();

        System.out.println(String.format("%d шт. по %.2f = %.2f", count, price, count * price));
        System.out.println(String.format("[%5d] [%-5d] [%05d]", count, count, count));
        System.out.println(String.format("[%10s] [%-10s]", item, item));
        System.out.println(String.format("%x %X %o %c %b %%", 255, 255, 8, 'ж', count > 0));
        System.out.println(String.format("%,d %+d %e", count * 1000, count, price));
        System.out.printf("%08.3f|%10.1f|%-10.1f|%n", price, price, price);

        StringBuilder out = new StringBuilder();
        Formatter formatter = new Formatter(out);
        for (int i = 1; i <= 3; i++) {
            formatter.format("%d:%s;", i, item.charAt(0));
        }
        formatter.flush();
        System.out.println(out);
        System.out.println(String.valueOf(price) + " " + Double.toString(count / 3.0));
    }
}
