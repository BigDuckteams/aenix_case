import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int a = in.nextInt();
        int b = in.nextInt();

        int sum = a + b;
        int diff = a - b;
        int prod = a * b;
        int quot = b != 0 ? a / b : 0;
        int rem = b != 0 ? a % b : 0;
        double ratio = b != 0 ? (double) a / b : Double.NaN;
        System.out.println(sum + " " + diff + " " + prod + " " + quot + " " + rem + " " + ratio);

        boolean both = a > 0 && b > 0;
        boolean either = a > 0 || b > 0;
        boolean exactlyOne = (a > 0) ^ (b > 0);
        System.out.println(both + " " + either + " " + exactlyOne + " " + !both);
        System.out.println((a == b) + " " + (a != b) + " " + (a < b) + " " + (a >= b));

        System.out.println((a & b) + " " + (a | b) + " " + (a ^ b) + " " + (~a));
        System.out.println((a << 2) + " " + (a >> 1) + " " + (a >>> 28));

        int x = a;
        x += b;
        x -= 1;
        x *= 2;
        x <<= 1;
        x %= 1000;
        x++;
        --x;
        System.out.println("x=" + x);

        String parity = a % 2 == 0 ? "чётное" : "нечётное";
        int max = a > b ? a : b;
        int precedence = a + b * 2 - (a - b) / 2;
        System.out.println(parity + " " + max + " " + precedence);
    }
}
