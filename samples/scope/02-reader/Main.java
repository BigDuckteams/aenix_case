import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

public class Main {
    public static void main(String[] args) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String first = reader.readLine();
        if (first == null) {
            System.out.println("ввод пуст");
            return;
        }
        int n = Integer.parseInt(first.trim());
        long sum = 0;
        for (int i = 0; i < n; i++) {
            String line = reader.readLine();
            if (line == null) {
                break;
            }
            String[] parts = line.trim().split("\\s+");
            for (String part : parts) {
                if (!part.isEmpty()) {
                    sum += Long.parseLong(part);
                }
            }
        }
        int extra = 0;
        String rest;
        while ((rest = reader.readLine()) != null) {
            extra += rest.length();
        }
        System.out.println("n = " + n + ", сумма = " + sum + ", лишних символов = " + extra);
    }
}
