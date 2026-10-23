import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Scanner;

/** Вне рамок кейса: java.time и файловые операции (рабочий каталог запуска — временный). */
public class Main {
    public static void main(String[] args) throws IOException {
        Scanner in = new Scanner(System.in, "UTF-8");
        int days = in.nextInt();
        String text = in.next();

        LocalDate start = LocalDate.of(2024, 2, 27);
        LocalDate end = start.plusDays(days);
        System.out.println(start + " -> " + end + " (" + ChronoUnit.DAYS.between(start, end) + " дн.)");
        System.out.println("високосный год: " + end.isLeapYear() + ", день недели: " + end.getDayOfWeek());

        Path file = Path.of("out-of-scope-demo.txt");
        Files.write(file, List.of(text, "вторая строка"), StandardCharsets.UTF_8);
        List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
        System.out.println("прочитано строк: " + lines.size() + ", первая: " + lines.get(0));
        Files.delete(file);
        System.out.println("файл существует: " + Files.exists(file));
    }
}
