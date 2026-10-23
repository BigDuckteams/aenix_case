import java.util.Arrays;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        int[] data = new int[n];
        for (int i = 0; i < n; i++) {
            data[i] = in.nextInt();
        }

        int[] sorted = data.clone();
        for (int i = 0; i < sorted.length; i++) {
            for (int j = 0; j + 1 < sorted.length - i; j++) {
                if (sorted[j] > sorted[j + 1]) {
                    int tmp = sorted[j];
                    sorted[j] = sorted[j + 1];
                    sorted[j + 1] = tmp;
                }
            }
        }
        System.out.println("исходный: " + Arrays.toString(data));
        System.out.println("отсортированный: " + Arrays.toString(sorted));

        int[][] matrix = {{1, 2, 3}, {4, 5, 6}};
        int[][] transposed = new int[3][2];
        for (int i = 0; i < 2; i++) {
            for (int j = 0; j < 3; j++) {
                transposed[j][i] = matrix[i][j];
            }
        }
        System.out.println(Arrays.deepToString(transposed));

        int[][] jagged = new int[3][];
        for (int i = 0; i < jagged.length; i++) {
            jagged[i] = new int[i + 1];
            Arrays.fill(jagged[i], i);
        }
        int total = 0;
        for (int[] row : jagged) {
            for (int value : row) {
                total += value;
            }
        }
        String[] words = {"один", "два", "три"};
        System.out.println(Arrays.deepToString(jagged) + " сумма=" + total + " слов=" + words.length);
    }
}
