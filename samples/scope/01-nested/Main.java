import java.util.Comparator;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

public class Main {
    private int base = 100;

    static class Pair {
        final int left;
        final int right;

        Pair(int left, int right) {
            this.left = left;
            this.right = right;
        }

        int sum() {
            return left + right;
        }
    }

    class Shifter {
        int shift(int value) {
            return value + base;
        }
    }

    interface Greeter {
        String greet(String name);
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        List<Pair> pairs = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            pairs.add(new Pair(in.nextInt(), in.nextInt()));
        }
        Main outer = new Main();
        Main.Shifter shifter = outer.new Shifter();

        class Doubler {
            int apply(int x) {
                return x * 2;
            }
        }
        Doubler doubler = new Doubler();

        Greeter greeter = new Greeter() {
            @Override
            public String greet(String name) {
                return "Привет, " + name + "!";
            }
        };

        pairs.sort(new Comparator<Pair>() {
            @Override
            public int compare(Pair a, Pair b) {
                return Integer.compare(b.sum(), a.sum());
            }
        });
        for (Pair pair : pairs) {
            System.out.println(pair.left + "+" + pair.right + "=" + pair.sum()
                    + " -> " + shifter.shift(doubler.apply(pair.sum())));
        }
        System.out.println(greeter.greet("мир"));
    }
}
