import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

public class Main {
    record Item(String name, String group, int price) {
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        List<Item> items = new java.util.ArrayList<>();
        for (int i = 0; i < n; i++) {
            items.add(new Item(in.next(), in.next(), in.nextInt()));
        }

        List<String> expensive = items.stream()
                .filter(item -> item.price() >= 100)
                .map(Item::name)
                .sorted()
                .collect(Collectors.toList());
        System.out.println("дорогие: " + expensive);

        int total = items.stream().mapToInt(Item::price).sum();
        Optional<Item> cheapest = items.stream().min((a, b) -> Integer.compare(a.price(), b.price()));
        System.out.println("всего: " + total + ", самый дешёвый: " + cheapest.map(Item::name).orElse("нет"));

        Map<String, Long> countByGroup = items.stream()
                .collect(Collectors.groupingBy(Item::group, TreeMap::new, Collectors.counting()));
        Map<String, Integer> sumByGroup = items.stream()
                .collect(Collectors.groupingBy(Item::group, TreeMap::new, Collectors.summingInt(Item::price)));
        System.out.println(countByGroup + " " + sumByGroup);

        Map<Boolean, List<String>> parts = items.stream()
                .collect(Collectors.partitioningBy(item -> item.price() > 50,
                        Collectors.mapping(Item::name, Collectors.toList())));
        System.out.println("дороже 50: " + parts.get(true) + ", остальные: " + parts.get(false));

        String joined = items.stream().map(Item::name).distinct().limit(3).collect(Collectors.joining(", ", "<", ">"));
        System.out.println(joined);
        Map<String, Integer> byName = items.stream()
                .collect(Collectors.toMap(Item::name, Item::price, Integer::sum, TreeMap::new));
        System.out.println(byName);

        System.out.println(IntStream.rangeClosed(1, n).map(x -> x * x).boxed().collect(Collectors.toList()));
        System.out.println(Arrays.stream(new int[] {4, 8, 15, 16, 23, 42}).filter(x -> x % 2 == 0).reduce(0, Integer::sum));
        System.out.println(items.stream().anyMatch(item -> item.group().equals("еда")) + " "
                + items.stream().allMatch(item -> item.price() > 0) + " " + items.stream().count());
        List<List<Integer>> nested = List.of(List.of(1, 2), List.of(3), List.of());
        System.out.println(nested.stream().flatMap(List::stream).map(x -> x * 2).collect(Collectors.toList()));
    }
}
