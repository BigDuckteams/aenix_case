import java.util.Scanner;

class Resource implements AutoCloseable {
    private final String name;

    Resource(String name) {
        this.name = name;
        System.out.println("открыт " + name);
    }

    void use(int value) {
        if (value < 0) {
            throw new IllegalArgumentException("отрицательное значение: " + value);
        }
        System.out.println(name + " обрабатывает " + value);
    }

    @Override
    public void close() {
        System.out.println("закрыт " + name);
    }
}

public class Main {
    static int divide(int a, int b) {
        try {
            return a / b;
        } catch (ArithmeticException e) {
            System.out.println("деление на ноль: " + e.getMessage());
            return 0;
        } finally {
            System.out.println("divide(" + a + ", " + b + ") завершён");
        }
    }

    static int parse(String text) {
        try {
            return Integer.parseInt(text);
        } catch (NumberFormatException | NullPointerException e) {
            return -1;
        }
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int a = in.nextInt();
        int b = in.nextInt();
        String text = in.next();
        System.out.println(divide(a, b));
        System.out.println(parse(text));
        try (Resource first = new Resource("A"); Resource second = new Resource("B")) {
            first.use(a);
            second.use(b);
        } catch (IllegalArgumentException e) {
            System.out.println("ошибка: " + e.getMessage());
        } finally {
            System.out.println("готово");
        }
    }
}
