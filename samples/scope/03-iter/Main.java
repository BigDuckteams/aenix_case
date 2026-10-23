import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Scanner;

class Range implements Iterable<Integer> {
    private final int from;
    private final int to;

    Range(int from, int to) {
        this.from = from;
        this.to = to;
    }

    @Override
    public Iterator<Integer> iterator() {
        return new Iterator<Integer>() {
            private int current = from;

            @Override
            public boolean hasNext() {
                return current < to;
            }

            @Override
            public Integer next() {
                return current++;
            }
        };
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int from = in.nextInt();
        int to = in.nextInt();

        List<Integer> numbers = new ArrayList<>();
        for (int value : new Range(from, to)) {
            numbers.add(value);
        }
        System.out.println("до: " + numbers);

        Iterator<Integer> it = numbers.iterator();
        while (it.hasNext()) {
            int value = it.next();
            if (value % 3 == 0) {
                it.remove();
            }
        }
        System.out.println("после: " + numbers);

        int sum = 0;
        for (Iterator<Integer> i = numbers.iterator(); i.hasNext(); ) {
            sum += i.next();
        }
        System.out.println("сумма: " + sum);
        Iterable<Integer> iterable = numbers;
        for (Integer value : iterable) {
            System.out.print(value + " ");
        }
        System.out.println();
    }
}
