import java.util.Optional;
import java.util.Scanner;

public class Main {
    static Optional<Integer> parse(String text) {
        try {
            return Optional.of(Integer.parseInt(text));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }

    static Optional<String> find(String key) {
        String value = key.equals("ключ") ? "значение" : null;
        return Optional.ofNullable(value);
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        String text = in.next();
        String key = in.next();

        Optional<Integer> number = parse(text);
        System.out.println(number.isPresent() + " " + number.isEmpty());
        System.out.println(number.map(v -> v * 2).orElse(-1));
        System.out.println(number.filter(v -> v > 10).map(String::valueOf).orElse("не больше десяти"));
        number.ifPresent(v -> System.out.println("число " + v));
        number.ifPresentOrElse(v -> System.out.println("есть"), () -> System.out.println("нет"));

        Optional<String> found = find(key);
        System.out.println(found.orElse("пусто") + " " + found.orElseGet(() -> "запасное"));
        System.out.println(found.map(String::length).orElse(0));
        try {
            System.out.println(found.orElseThrow(() -> new IllegalStateException("не найдено: " + key)));
        } catch (IllegalStateException e) {
            System.out.println(e.getMessage());
        }
        System.out.println(Optional.empty().equals(Optional.empty()) + " " + Optional.of("a").equals(Optional.of("a")));
    }
}
