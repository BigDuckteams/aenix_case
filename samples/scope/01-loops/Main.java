import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();

        int sum = 0;
        for (int i = 1; i <= n; i++) {
            sum += i;
        }
        System.out.println("сумма 1.." + n + " = " + sum);

        int[] values = {3, 1, 4, 1, 5, 9, 2, 6};
        int max = Integer.MIN_VALUE;
        for (int v : values) {
            if (v > max) {
                max = v;
            }
        }
        System.out.println("максимум = " + max);

        int digits = 0;
        int rest = n;
        while (rest > 0) {
            digits++;
            rest /= 10;
        }
        System.out.println("цифр: " + digits);

        int steps = 0;
        int x = n;
        do {
            x = x / 2;
            steps++;
        } while (x > 0);
        System.out.println("делений пополам: " + steps);

        StringBuilder table = new StringBuilder();
        outer:
        for (int i = 1; i <= 3; i++) {
            for (int j = 1; j <= 3; j++) {
                if (i * j > n) {
                    continue outer;
                }
                table.append(i * j).append(' ');
            }
            table.append("| ");
        }
        System.out.println(table.toString().trim());
    }
}
