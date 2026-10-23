import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        int[] array = new int[n];
        for (int i = 0; i < n; i++) {
            array[i] = in.nextInt();
        }
        int[] copy = Arrays.copyOf(array, n + 2);
        Arrays.sort(array);
        System.out.println(Arrays.toString(array) + " " + Arrays.toString(copy));
        System.out.println("равны: " + Arrays.equals(array, copy) + ", бинарный поиск 5: " + Arrays.binarySearch(array, 5));
        int[] filled = new int[4];
        Arrays.fill(filled, 7);
        System.out.println(Arrays.toString(filled) + " " + Arrays.stream(array).sum());

        List<Integer> list = new ArrayList<>(Arrays.asList(3, 1, 2));
        for (int value : array) {
            list.add(value);
        }
        Collections.sort(list);
        System.out.println(list + " max=" + Collections.max(list) + " min=" + Collections.min(list));
        Collections.reverse(list);
        Collections.swap(list, 0, list.size() - 1);
        System.out.println(list + " частота 1: " + Collections.frequency(list, 1));

        List<Integer> readOnly = Collections.unmodifiableList(list);
        try {
            readOnly.add(100);
        } catch (UnsupportedOperationException e) {
            System.out.println("нельзя изменить");
        }
        System.out.println(Collections.nCopies(3, "ab") + " " + Collections.emptyList() + " " + readOnly.size());
    }
}
