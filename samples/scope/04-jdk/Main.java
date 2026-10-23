import java.util.ArrayList;
import java.util.InputMismatchException;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Scanner;

public class Main {
    static void attempt(int step, String text) {
        try {
            switch (step) {
                case 0:
                    System.out.println(Integer.parseInt(text));
                    break;
                case 1:
                    System.out.println(10 / Integer.parseInt(text));
                    break;
                case 2:
                    String value = text.equals("null") ? null : text;
                    System.out.println(value.length());
                    break;
                case 3:
                    int[] array = new int[3];
                    System.out.println(array[Integer.parseInt(text)]);
                    break;
                case 4:
                    List<String> list = new ArrayList<>();
                    list.add(text);
                    System.out.println(list.get(1));
                    break;
                case 5:
                    if (text.length() < 3) {
                        throw new IllegalArgumentException("слишком короткое слово: " + text);
                    }
                    System.out.println("слово принято");
                    break;
                default:
                    new ArrayList<String>().iterator().next();
            }
        } catch (NumberFormatException e) {
            System.out.println("шаг " + step + ": NumberFormatException " + e.getMessage());
        } catch (ArithmeticException e) {
            System.out.println("шаг " + step + ": ArithmeticException " + e.getMessage());
        } catch (NullPointerException e) {
            System.out.println("шаг " + step + ": NullPointerException");
        } catch (IndexOutOfBoundsException e) {
            System.out.println("шаг " + step + ": IndexOutOfBoundsException");
        } catch (IllegalArgumentException e) {
            System.out.println("шаг " + step + ": IllegalArgumentException " + e.getMessage());
        } catch (NoSuchElementException e) {
            System.out.println("шаг " + step + ": NoSuchElementException");
        }
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        String text = in.next();
        for (int step = 0; step <= 6; step++) {
            attempt(step, text);
        }
        try {
            System.out.println(in.nextInt());
        } catch (InputMismatchException e) {
            System.out.println("InputMismatchException");
        } catch (NoSuchElementException e) {
            System.out.println("ввод закончился");
        }
    }
}
