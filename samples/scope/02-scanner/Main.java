import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int count = in.nextInt();
        double total = 0;
        for (int i = 0; i < count; i++) {
            total += in.nextDouble();
        }
        in.nextLine();
        String title = in.nextLine();
        String word = in.next();
        System.out.println("сумма = " + total);
        System.out.println("заголовок = «" + title + "»");
        System.out.println("слово = " + word);

        int numbers = 0;
        int words = 0;
        while (in.hasNext()) {
            if (in.hasNextInt()) {
                numbers += in.nextInt();
            } else {
                in.next();
                words++;
            }
        }
        System.out.println("числа = " + numbers + ", слов = " + words);
        System.out.println(in.hasNextLine() + " " + in.hasNext());
    }
}
