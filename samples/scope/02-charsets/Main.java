import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, StandardCharsets.UTF_8);
        String text = in.hasNextLine() ? in.nextLine() : "";
        PrintStream out = new PrintStream(System.out, true, StandardCharsets.UTF_8);

        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        byte[] latin = text.getBytes(StandardCharsets.ISO_8859_1);
        out.println("символов: " + text.length() + ", байт UTF-8: " + utf8.length);
        out.println("байт ISO-8859-1: " + latin.length);

        String restored = new String(utf8, StandardCharsets.UTF_8);
        out.println("восстановлено: " + restored + " (" + restored.equals(text) + ")");
        out.println("через ISO-8859-1 совпадает: " + new String(latin, StandardCharsets.ISO_8859_1).equals(text));

        StringBuilder hex = new StringBuilder();
        for (int i = 0; i < Math.min(utf8.length, 6); i++) {
            hex.append(String.format("%02x ", utf8[i]));
        }
        out.println("первые байты: " + hex.toString().trim());
        out.println("кодовых точек: " + text.codePointCount(0, text.length()));
    }
}
