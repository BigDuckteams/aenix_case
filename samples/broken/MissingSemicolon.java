// broken: syntax
import java.util.Scanner;

public class MissingSemicolon {
    static int twice(int value) {
        return value * 2
    }

    static int total(int[] values) {
        int sum = 0;
        for (int v : values) {
            sum += v;
        }
        return sum;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int n = in.nextInt();
        System.out.println(twice(n));
        System.out.println(total(new int[] {1, 2, 3}));
    }
}
