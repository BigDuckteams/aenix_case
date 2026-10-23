import java.util.Scanner;

public class Main {
    static String grade(int score) {
        if (score >= 90) {
            return "отлично";
        } else if (score >= 70) {
            return "хорошо";
        } else if (score >= 50) {
            return "удовлетворительно";
        } else {
            return "неудовлетворительно";
        }
    }

    static int daysInMonth(int month) {
        switch (month) {
            case 2:
                return 28;
            case 4:
            case 6:
            case 9:
            case 11:
                return 30;
            default:
                return 31;
        }
    }

    static String season(int month) {
        return switch (month) {
            case 12, 1, 2 -> "зима";
            case 3, 4, 5 -> "весна";
            case 6, 7, 8 -> "лето";
            default -> "осень";
        };
    }

    static int weight(String word) {
        return switch (word) {
            case "один" -> 1;
            case "два" -> 2;
            default -> {
                int length = word.length();
                yield length * 10;
            }
        };
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int score = in.nextInt();
        int month = in.nextInt();
        String word = in.next();
        System.out.println(grade(score));
        System.out.println(daysInMonth(month) + " " + season(month));
        System.out.println(weight(word));
    }
}
