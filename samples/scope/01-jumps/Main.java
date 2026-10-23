import java.util.Scanner;

public class Main {
    static int firstNegative(int[] values) {
        for (int i = 0; i < values.length; i++) {
            if (values[i] < 0) {
                return i;
            }
        }
        return -1;
    }

    static boolean hasPair(int[] values, int target) {
        boolean found = false;
        search:
        for (int i = 0; i < values.length; i++) {
            for (int j = i + 1; j < values.length; j++) {
                if (values[i] + values[j] == target) {
                    found = true;
                    break search;
                }
            }
        }
        return found;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        int[] values = new int[n];
        for (int i = 0; i < n; i++) {
            values[i] = in.nextInt();
        }
        int target = in.nextInt();

        int evenSum = 0;
        for (int v : values) {
            if (v % 2 != 0) {
                continue;
            }
            if (v > 100) {
                break;
            }
            evenSum += v;
        }
        System.out.println("сумма чётных до 100: " + evenSum);
        System.out.println("первый отрицательный: " + firstNegative(values));
        System.out.println("пара для " + target + ": " + hasPair(values, target));

        int i = 0;
        while (true) {
            if (i >= n) {
                break;
            }
            i += 2;
        }
        System.out.println("i=" + i);
    }
}
