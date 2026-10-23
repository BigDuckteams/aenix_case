import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Scanner;
import java.util.Set;
import java.util.TreeSet;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        Set<String> hash = new HashSet<>();
        Set<String> linked = new LinkedHashSet<>();
        TreeSet<String> tree = new TreeSet<>();
        int duplicates = 0;
        while (in.hasNext()) {
            String word = in.next();
            if (!hash.add(word)) {
                duplicates++;
            }
            linked.add(word);
            tree.add(word);
        }
        System.out.println("уникальных: " + hash.size() + ", повторов: " + duplicates);
        System.out.println("порядок ввода: " + linked);
        System.out.println("по алфавиту: " + tree);
        System.out.println("contains 'да': " + hash.contains("да"));
        if (!tree.isEmpty()) {
            System.out.println("первое " + tree.first() + ", последнее " + tree.last());
            System.out.println("floor 'м': " + tree.floor("м") + ", ceiling 'м': " + tree.ceiling("м"));
            System.out.println("до 'м': " + tree.headSet("м") + ", с 'м': " + tree.tailSet("м"));
        }
        Set<String> other = new TreeSet<>(java.util.Arrays.asList("да", "нет", "мир"));
        Set<String> common = new TreeSet<>(tree);
        common.retainAll(other);
        Set<String> union = new TreeSet<>(tree);
        union.addAll(other);
        Set<String> onlyHere = new TreeSet<>(tree);
        onlyHere.removeAll(other);
        System.out.println("пересечение " + common + ", объединение " + union + ", разность " + onlyHere);
    }
}
