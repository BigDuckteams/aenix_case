import java.util.Scanner;

class ConfigError extends RuntimeException {
    private static final long serialVersionUID = 1L;

    ConfigError(String message) {
        super(message);
    }
}

public class Main {
    static int validate(int level) {
        if (level > 5) {
            throw new ConfigError("уровень " + level + " недопустим");
        }
        return level * 2;
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int total = 0;
        while (in.hasNextInt()) {
            int level = in.nextInt();
            System.out.println("проверка " + level);
            total += validate(level);
            System.out.println("итого " + total);
        }
        System.out.println("завершено без ошибок: " + total);
    }
}
