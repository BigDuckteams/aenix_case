import java.util.Scanner;

class Counter {
    private final String name;
    private int value;

    Counter(String name) {
        this.name = name;
    }

    void add(int delta) {
        value += delta;
    }

    int getValue() {
        return value;
    }

    String getName() {
        return name;
    }
}

class Report {
    static String line(Counter counter) {
        return counter.getName() + ": " + counter.getValue();
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        String name = in.hasNext() ? in.next() : "без имени";
        Counter counter = new Counter(name);
        while (in.hasNextInt()) {
            counter.add(in.nextInt());
        }
        System.out.println(Report.line(counter));
    }
}
