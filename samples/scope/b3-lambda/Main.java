import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;
import java.util.function.BiFunction;
import java.util.function.Consumer;
import java.util.function.Function;
import java.util.function.Predicate;
import java.util.function.Supplier;
import java.util.function.UnaryOperator;

public class Main {
    static int applyTwice(Function<Integer, Integer> function, int value) {
        return function.apply(function.apply(value));
    }

    static List<Integer> filter(List<Integer> source, Predicate<Integer> predicate) {
        List<Integer> result = new ArrayList<>();
        for (Integer item : source) {
            if (predicate.test(item)) {
                result.add(item);
            }
        }
        return result;
    }

    static boolean isEven(int value) {
        return value % 2 == 0;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        List<Integer> numbers = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            numbers.add(in.nextInt());
        }
        int threshold = in.nextInt();

        Function<Integer, Integer> square = x -> x * x;
        Function<Integer, Integer> plusOne = x -> x + 1;
        BiFunction<Integer, Integer, Integer> add = (a, b) -> a + b;
        UnaryOperator<String> shout = s -> s.toUpperCase() + "!";
        Supplier<String> greeting = () -> "привет";
        Consumer<Integer> printer = value -> System.out.print("[" + value + "]");
        Predicate<Integer> big = value -> value > threshold;

        System.out.println(applyTwice(square, 3) + " " + square.andThen(plusOne).apply(4)
                + " " + square.compose(plusOne).apply(4) + " " + add.apply(2, 5));
        System.out.println(shout.apply(greeting.get()));
        System.out.println(filter(numbers, big) + " " + filter(numbers, Main::isEven)
                + " " + filter(numbers, big.negate().and(Main::isEven)));
        numbers.forEach(printer);
        System.out.println();
        numbers.removeIf(value -> value < 0);
        numbers.replaceAll(value -> value * 10);
        System.out.println(numbers);

        int[] counter = {0};
        Consumer<Integer> increment = step -> counter[0] += step;
        for (int i = 0; i < n; i++) {
            increment.accept(1);
        }
        Supplier<List<String>> factory = ArrayList::new;
        List<String> created = factory.get();
        created.add("пусто");
        Function<String, Integer> length = String::length;
        System.out.println(counter[0] + " " + created + " " + length.apply("слово"));
    }
}
