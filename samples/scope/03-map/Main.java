import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        Map<String, Integer> counts = new HashMap<>();
        Map<String, List<Integer>> positions = new LinkedHashMap<>();
        int position = 0;
        while (in.hasNext()) {
            String word = in.next();
            counts.put(word, counts.getOrDefault(word, 0) + 1);
            positions.computeIfAbsent(word, key -> new ArrayList<>()).add(position);
            position++;
        }
        Map<String, Integer> sorted = new TreeMap<>(counts);
        for (Map.Entry<String, Integer> entry : sorted.entrySet()) {
            System.out.println(entry.getKey() + " -> " + entry.getValue());
        }
        System.out.println("позиции: " + positions);

        Map<Integer, Integer> byLength = new TreeMap<>();
        for (String word : counts.keySet()) {
            byLength.merge(word.length(), counts.get(word), Integer::sum);
        }
        System.out.println("по длине: " + byLength);
        System.out.println("есть 'да': " + counts.containsKey("да") + ", значений: " + counts.values().stream().mapToInt(Integer::intValue).sum());
        counts.remove("да");
        System.out.println("после удаления: " + new TreeMap<>(counts) + " " + counts.size());
    }
}
