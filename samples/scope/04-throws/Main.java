import java.io.IOException;
import java.util.Scanner;

public class Main {
    static int readValue(String text) throws IOException {
        try {
            return Integer.parseInt(text);
        } catch (NumberFormatException e) {
            throw new IOException("неверное значение «" + text + "»", e);
        }
    }

    static int middle(String a, String b) throws IOException {
        int x = readValue(a);
        int y = readValue(b);
        return (x + y) / 2;
    }

    static void top(String a, String b) throws Exception {
        int m = middle(a, b);
        if (m > 100) {
            throw new Exception("слишком большое среднее: " + m);
        }
        System.out.println("среднее " + m);
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        while (in.hasNext()) {
            String a = in.next();
            String b = in.next();
            try {
                top(a, b);
            } catch (IOException e) {
                System.out.println("ввод-вывод: " + e.getMessage() + " (причина: " + e.getCause().getClass().getSimpleName() + ")");
            } catch (Exception e) {
                System.out.println("общее: " + e.getMessage());
            }
        }
    }
}
