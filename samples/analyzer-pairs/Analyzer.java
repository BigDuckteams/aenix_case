import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

/**
 * Пример со слайда 5 кейса: вложенные циклы по одним и тем же элементам.
 *
 * analyze() — фрагмент со слайда без изменений: пара (a, b) с одинаковым id попадает в merge(a, b),
 * поэтому одинаковые пары обрабатываются повторно, а время растёт как O(n²).
 * findPairs() — перебор пар (i < j): второй источник O(n²).
 */
public class Analyzer {

    static class Item {
        private final String id;
        private final int weight;
        private int merged;

        Item(String id, int weight) {
            this.id = id;
            this.weight = weight;
        }

        String id() {
            return id;
        }

        int weight() {
            return weight;
        }

        int merged() {
            return merged;
        }

        void absorb(int amount) {
            merged += amount;
        }
    }

    static void merge(Item a, Item b) {
        a.absorb(b.weight());
    }

    static void analyze(List<Item> items) {
        for (Item a : items) {
            for (Item b : items) {
                if (a.id().equals(b.id())) {
                    merge(a, b);
                }
            }
        }
    }

    static List<int[]> findPairs(List<Item> items, int target) {
        List<int[]> pairs = new ArrayList<>();
        for (int i = 0; i < items.size(); i++) {
            for (int j = i + 1; j < items.size(); j++) {
                if (items.get(i).weight() + items.get(j).weight() == target) {
                    pairs.add(new int[] {i, j});
                }
            }
        }
        return pairs;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        List<Item> items = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            String id = in.next();
            int weight = in.nextInt();
            items.add(new Item(id, weight));
        }
        int target = in.nextInt();

        analyze(items);
        int shared = 0;
        for (Item item : items) {
            System.out.println(item.id() + ": " + item.weight() + " -> " + item.merged());
            if (item.merged() != item.weight()) {
                shared++;
            }
        }
        System.out.println("записей: " + items.size() + ", с общим id: " + shared);

        List<int[]> pairs = findPairs(items, target);
        System.out.println("пар с суммой " + target + ": " + pairs.size());
        int shown = Math.min(pairs.size(), 5);
        for (int i = 0; i < shown; i++) {
            int[] pair = pairs.get(i);
            System.out.println(items.get(pair[0]).id() + " + " + items.get(pair[1]).id());
        }
    }
}
