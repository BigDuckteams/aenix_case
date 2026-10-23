import java.io.IOException;
import java.util.Scanner;

public class Main {
    static String load(String name) throws IOException {
        if (name.isEmpty()) {
            throw new IOException("пустое имя ресурса");
        }
        if (name.startsWith("!")) {
            throw new IOException("ресурс недоступен: " + name.substring(1));
        }
        return "содержимое " + name;
    }

    static int checkAge(int age) {
        if (age < 0) {
            throw new IllegalArgumentException("возраст не может быть отрицательным");
        }
        return age;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        for (int i = 0; i < n; i++) {
            String name = in.next();
            if (name.equals("-")) {
                name = "";
            }
            try {
                System.out.println(load(name));
            } catch (IOException e) {
                System.out.println("проверяемое: " + e.getMessage());
            }
        }
        int age = in.nextInt();
        try {
            System.out.println("возраст " + checkAge(age));
        } catch (RuntimeException e) {
            System.out.println("непроверяемое: " + e.getMessage());
        }
        try {
            Object value = "строка";
            Integer wrong = (Integer) value;
            System.out.println(wrong);
        } catch (ClassCastException e) {
            System.out.println("ошибка приведения типа");
        }
    }
}
