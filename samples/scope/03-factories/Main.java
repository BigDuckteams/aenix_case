import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.Set;
import java.util.TreeSet;

interface Action {
    void run();
}

public class Main {
    static void tryModify(String title, Action action) {
        try {
            action.run();
            System.out.println(title + ": изменено");
        } catch (UnsupportedOperationException e) {
            System.out.println(title + ": нельзя изменить");
        }
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int extra = in.nextInt();

        List<Integer> list = List.of(3, 1, 2, extra);
        Set<String> set = Set.of("а", "б", "в");
        Map<String, Integer> map = Map.of("один", 1, "два", 2);

        System.out.println(list + " размер " + list.size());
        System.out.println(new TreeSet<>(set) + " " + set.contains("б") + " " + set.contains("г"));
        System.out.println(map.get("два") + " " + map.getOrDefault("три", 0) + " " + new TreeSet<>(map.keySet()));

        tryModify("List.of", () -> list.add(5));
        tryModify("Set.of", () -> set.remove("а"));
        tryModify("Map.of", () -> map.put("три", 3));

        List<Integer> mutable = new ArrayList<>(list);
        mutable.add(100);
        List<Integer> snapshot = List.copyOf(mutable);
        mutable.add(200);
        System.out.println(mutable + " " + snapshot);
        tryModify("копия", () -> snapshot.set(0, 0));
        for (int value : List.of(10, 20)) {
            System.out.print(value + ";");
        }
        System.out.println();
    }
}
