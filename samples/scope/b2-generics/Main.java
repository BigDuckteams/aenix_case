import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

interface Container<T> {
    void put(T item);

    T get(int index);

    int size();
}

class Box<T> implements Container<T> {
    private final List<T> items = new ArrayList<>();

    @Override
    public void put(T item) {
        items.add(item);
    }

    @Override
    public T get(int index) {
        return items.get(index);
    }

    @Override
    public int size() {
        return items.size();
    }
}

class Pair<K extends Comparable<K>, V> {
    final K key;
    final V value;

    Pair(K key, V value) {
        this.key = key;
        this.value = value;
    }

    @Override
    public String toString() {
        return key + "=" + value;
    }
}

public class Main {
    static <T extends Comparable<T>> T maxOf(List<T> items) {
        T best = items.get(0);
        for (T item : items) {
            if (item.compareTo(best) > 0) {
                best = item;
            }
        }
        return best;
    }

    static double sum(List<? extends Number> numbers) {
        double total = 0;
        for (Number number : numbers) {
            total += number.doubleValue();
        }
        return total;
    }

    static void fill(List<? super Integer> target, int count) {
        for (int i = 0; i < count; i++) {
            target.add(i);
        }
    }

    static <A, B> List<B> convert(List<A> source, java.util.function.Function<A, B> mapper) {
        List<B> result = new ArrayList<>();
        for (A item : source) {
            result.add(mapper.apply(item));
        }
        return result;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        Box<Integer> numbers = new Box<>();
        Box<String> words = new Box<>();
        for (int i = 0; i < n; i++) {
            numbers.put(in.nextInt());
            words.put(in.next());
        }
        List<Integer> list = new ArrayList<>();
        List<String> names = new ArrayList<>();
        for (int i = 0; i < numbers.size(); i++) {
            list.add(numbers.get(i));
            names.add(words.get(i));
        }
        if (!list.isEmpty()) {
            System.out.println("максимум: " + maxOf(list) + ", слово: " + maxOf(names));
        }
        System.out.println("сумма: " + sum(list));
        List<Object> objects = new ArrayList<>();
        fill(objects, 3);
        System.out.println(objects + " " + convert(names, String::length));
        Pair<String, Integer> pair = new Pair<>("ключ", n);
        System.out.println(pair);
    }
}
