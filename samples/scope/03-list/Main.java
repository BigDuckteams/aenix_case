import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedList;
import java.util.List;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        List<Integer> list = new ArrayList<>();
        while (in.hasNextInt()) {
            list.add(in.nextInt());
        }
        System.out.println("список: " + list + ", размер " + list.size());
        if (!list.isEmpty()) {
            list.set(0, list.get(0) * 10);
            list.add(1, 99);
            list.remove(Integer.valueOf(99));
            list.remove(list.size() - 1);
        }
        System.out.println("после правок: " + list);
        System.out.println("contains 5: " + list.contains(5) + ", indexOf 5: " + list.indexOf(5));

        List<Integer> sorted = new ArrayList<>(list);
        Collections.sort(sorted);
        System.out.println("отсортирован: " + sorted);
        if (sorted.size() >= 3) {
            System.out.println("подсписок: " + sorted.subList(1, 3));
        }

        LinkedList<String> queue = new LinkedList<>();
        for (int i = 0; i < list.size(); i++) {
            queue.addLast("e" + list.get(i));
        }
        queue.addFirst("начало");
        System.out.println("очередь: " + queue + " первый=" + queue.getFirst() + " последний=" + queue.peekLast());
        if (!queue.isEmpty()) {
            queue.removeFirst();
        }
        int total = 0;
        for (int value : list) {
            total += value;
        }
        System.out.println("сумма " + total + ", в очереди " + queue.size());
    }
}
