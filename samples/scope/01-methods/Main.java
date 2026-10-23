import java.util.Scanner;

public class Main {
    static int sum(int a, int b) {
        return a + b;
    }

    static double sum(double a, double b) {
        return a + b;
    }

    static int sum(int... values) {
        int total = 0;
        for (int v : values) {
            total += v;
        }
        return total;
    }

    static long factorial(int n) {
        if (n <= 1) {
            return 1;
        }
        return n * factorial(n - 1);
    }

    static int fib(int n) {
        return n < 2 ? n : fib(n - 1) + fib(n - 2);
    }

    static int gcd(int a, int b) {
        return b == 0 ? a : gcd(b, a % b);
    }

    static long power(long base, int exponent) {
        if (exponent == 0) {
            return 1;
        }
        long half = power(base, exponent / 2);
        return exponent % 2 == 0 ? half * half : half * half * base;
    }

    int instanceCounter;

    int next() {
        return ++instanceCounter;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        System.out.println(sum(n, 2) + " " + sum(n + 0.5, 2.25) + " " + sum() + " " + sum(1, 2, 3, n));
        System.out.println(n + "! = " + factorial(n));
        System.out.println("fib(" + n + ") = " + fib(n));
        System.out.println("gcd = " + gcd(n * 6, 48) + ", 2^n = " + power(2, n));
        Main m = new Main();
        m.next();
        System.out.println("next = " + m.next());
    }
}
