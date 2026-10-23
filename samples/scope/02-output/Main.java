import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        String name = in.hasNextLine() ? in.nextLine() : "аноним";
        System.out.print("Привет, ");
        System.out.print(name);
        System.out.println("!");
        System.out.println();
        System.out.println(42);
        System.out.println(3.5);
        System.out.println('ж');
        System.out.println(true);
        System.out.println(new int[0].length);
        System.out.printf("%s прислал %d сообщений%n", name, name.length());
        for (int i = 1; i <= 3; i++) {
            System.out.print(i);
            System.out.print(i < 3 ? ", " : "\n");
        }
        System.err.println("Предупреждение: это сообщение идёт в stderr");
        System.err.printf("Код %d%n", 7);
        System.out.println("конец");
    }
}
