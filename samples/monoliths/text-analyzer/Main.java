import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Анализатор текста: хранит строки документа и считает по ним статистику.
 *
 * Команды читаются из стандартного ввода построчно; текст команды add и строки пакета load
 * могут содержать кириллицу. Весь код собран в одном классе: разбор команд, анализ, преобразования
 * текста и вывод. Пример монолита для проверки разбора, диагностики и декомпозиции.
 */
public class Main {

    private static final int MAX_LINES = 5000;
    private static final int MAX_LINE_LENGTH = 200;
    private static final int SHORT_WORD = 3;
    private static final int LONG_WORD = 9;
    private static final String VOWELS = "аеёиоуыэюяaeiouy";
    private static final String CONJUNCTION = "и";
    private static final String LONG_LABEL = "Длинное";

    private final List<String> lines = new ArrayList<>();
    private final List<String> stopWords = new ArrayList<>();
    private final List<String> history = new ArrayList<>();
    private int commandCount;
    private int errorCount;

    public static void main(String[] args) {
        Main app = new Main();
        try (Scanner in = new Scanner(System.in, StandardCharsets.UTF_8)) {
            app.run(in);
        }
        app.printFooter();
    }

    // ------------------------------------------------------------------
    // Основной цикл и разбор команд
    // ------------------------------------------------------------------

    void run(Scanner in) {
        printHeader();
        while (in.hasNextLine()) {
            String line = in.nextLine().trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            commandCount++;
            history.add(line);
            try {
                if (!processCommand(line, in)) {
                    break;
                }
            } catch (TextException e) {
                errorCount++;
                System.out.println("Ошибка текста: " + e.getMessage());
            } catch (LimitExceededException e) {
                errorCount++;
                System.out.println("Превышен лимит: " + e.getMessage());
            }
        }
    }

    private boolean processCommand(String line, Scanner in) throws TextException {
        String command = firstWord(line).toLowerCase();
        String rest = restOf(line);
        switch (command) {
            case "add":
                addLine(rest);
                break;
            case "load": {
                int count = parseInt(rest, "число строк");
                int loaded = readLines(in, count);
                System.out.printf("Загружено строк: %d из %d%n", loaded, count);
                break;
            }
            case "clear":
                lines.clear();
                System.out.println("Документ очищен");
                break;
            case "lines":
                printLines(lines);
                break;
            case "words":
                printWords();
                break;
            case "freq":
                printFrequencies(parseInt(rest, "количество"));
                break;
            case "find":
                printOccurrences(rest);
                break;
            case "replace": {
                String[] pair = rest.split(" ");
                if (pair.length < 2) {
                    throw new TextException("нужно два слова: что заменить и на что");
                }
                System.out.println("Замен: " + replaceWord(pair[0], pair[1]));
                break;
            }
            case "stop":
                handleStop(rest);
                break;
            case "dedupe":
                System.out.println("Удалено повторов: " + dedupeLines());
                break;
            case "anagrams":
                printAnagrams();
                break;
            case "palindromes":
                printPalindromes();
                break;
            case "stats":
                printStats();
                break;
            case "wrap":
                printWrapped(parseInt(rest, "ширина"));
                break;
            case "caesar":
                printCaesar(parseInt(rest, "сдвиг"));
                break;
            case "sentences":
                System.out.println("Предложений: " + countSentences());
                break;
            case "report":
                printReport();
                break;
            case "history":
                printHistory();
                break;
            case "boom":
                throw new IllegalStateException("Принудительное завершение по команде boom");
            case "quit":
            case "exit":
                return false;
            default:
                errorCount++;
                System.out.println("Неизвестная команда: " + command);
        }
        return true;
    }

    static String firstWord(String line) {
        int space = line.indexOf(' ');
        return space < 0 ? line : line.substring(0, space);
    }

    static String restOf(String line) {
        int space = line.indexOf(' ');
        return space < 0 ? "" : line.substring(space + 1).trim();
    }

    private int parseInt(String token, String what) throws TextException {
        try {
            return Integer.parseInt(token.trim());
        } catch (NumberFormatException e) {
            throw new TextException("«" + token + "» не число (" + what + ")");
        }
    }

    private int readLines(Scanner in, int count) {
        int loaded = 0;
        for (int i = 0; i < count && in.hasNextLine(); i++) {
            String raw = in.nextLine();
            try {
                addLine(raw);
                loaded++;
            } catch (TextException e) {
            }
        }
        return loaded;
    }

    private void handleStop(String rest) throws TextException {
        String[] parts = rest.split(" ");
        if (parts[0].equals("add") && parts.length > 1) {
            for (int i = 1; i < parts.length; i++) {
                if (!stopWords.contains(parts[i].toLowerCase())) {
                    stopWords.add(parts[i].toLowerCase());
                }
            }
            System.out.println("Стоп-слов: " + stopWords.size());
        } else if (parts[0].equals("list")) {
            System.out.println("Стоп-слова: " + stopWords);
        } else if (parts[0].equals("apply")) {
            System.out.println("Удалено слов: " + removeStopWords());
        } else {
            throw new TextException("stop add <слова> | stop list | stop apply");
        }
    }

    // ------------------------------------------------------------------
    // Хранение
    // ------------------------------------------------------------------

    void addLine(String raw) throws TextException {
        String text = raw.trim();
        if (text.isEmpty()) {
            throw new TextException("пустая строка");
        }
        if (text.length() > MAX_LINE_LENGTH) {
            throw new TextException("строка длиннее " + MAX_LINE_LENGTH + " символов");
        }
        if (lines.size() >= MAX_LINES) {
            throw new LimitExceededException("в документе уже " + MAX_LINES + " строк");
        }
        lines.add(text);
    }

    // ------------------------------------------------------------------
    // Разбор текста на слова
    // ------------------------------------------------------------------

    static List<String> splitWords(String text) {
        List<String> words = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (Character.isLetterOrDigit(c) || c == '-' || c == '\'') {
                current.append(c);
            } else if (current.length() > 0) {
                words.add(current.toString());
                current.setLength(0);
            }
        }
        if (current.length() > 0) {
            words.add(current.toString());
        }
        return words;
    }

    List<String> allWords() {
        List<String> words = new ArrayList<>();
        for (String line : lines) {
            for (String word : splitWords(line)) {
                words.add(word.toLowerCase());
            }
        }
        return words;
    }

    List<String> uniqueWords() {
        List<String> unique = new ArrayList<>();
        for (String word : allWords()) {
            if (!unique.contains(word)) {
                unique.add(word);
            }
        }
        return unique;
    }

    WordKind classify(String word) {
        if (word.length() <= SHORT_WORD) {
            return WordKind.SHORT;
        }
        if (word.length() >= LONG_WORD) {
            return WordKind.LONG;
        }
        return WordKind.NORMAL;
    }

    boolean isConjunction(String word) {
        return word.toLowerCase() == CONJUNCTION;
    }

    // ------------------------------------------------------------------
    // Анализ
    // ------------------------------------------------------------------

    int countVowels(String text) {
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = Character.toLowerCase(text.charAt(i));
            if (Character.isLetter(c) && VOWELS.indexOf(c) >= 0) {
                count++;
            }
        }
        return count;
    }

    int countConsonants(String text) {
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = Character.toLowerCase(text.charAt(i));
            if (Character.isLetter(c) && VOWELS.indexOf(c) < 0) {
                count++;
            }
        }
        return count;
    }

    int countDigits(String text) {
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (Character.isDigit(c)) {
                count++;
            }
        }
        return count;
    }

    int totalChars() {
        int total = 0;
        for (String line : lines) {
            total += line.length();
        }
        return total;
    }

    int totalVowels() {
        int total = 0;
        for (String line : lines) {
            total += countVowels(line);
        }
        return total;
    }

    int totalConsonants() {
        int total = 0;
        for (String line : lines) {
            total += countConsonants(line);
        }
        return total;
    }

    int totalDigits() {
        int total = 0;
        for (String line : lines) {
            total += countDigits(line);
        }
        return total;
    }

    int countSentences() {
        int count = 0;
        for (String line : lines) {
            for (int i = 0; i < line.length(); i++) {
                char c = line.charAt(i);
                if (c == '.' || c == '!' || c == '?') {
                    count++;
                }
            }
        }
        return count;
    }

    String longestWord() {
        String best = "";
        for (String word : allWords()) {
            if (word.length() > best.length()) {
                best = word;
            }
        }
        return best;
    }

    double averageWordLength() {
        List<String> words = allWords();
        if (words.isEmpty()) {
            return 0;
        }
        int total = 0;
        for (String word : words) {
            total += word.length();
        }
        return (double) total / words.size();
    }

    Map<String, Integer> wordFrequencies() {
        Map<String, Integer> counts = new TreeMap<>();
        for (String word : allWords()) {
            counts.merge(word, 1, Integer::sum);
        }
        return counts;
    }

    List<Map.Entry<String, Integer>> topWords(int n) {
        List<Map.Entry<String, Integer>> entries = new ArrayList<>(wordFrequencies().entrySet());
        Comparator<Map.Entry<String, Integer>> byCount = Map.Entry.comparingByValue();
        return topN(entries, byCount.reversed().thenComparing(Map.Entry.comparingByKey()), n);
    }

    static <T> List<T> topN(List<T> items, Comparator<? super T> order, int n) {
        List<T> sorted = new ArrayList<>(items);
        sorted.sort(order);
        return new ArrayList<>(sorted.subList(0, Math.min(Math.max(n, 0), sorted.size())));
    }

    static <T extends Comparable<T>> T maxOf(List<T> items, T fallback) {
        T best = fallback;
        for (T item : items) {
            if (item.compareTo(best) > 0) {
                best = item;
            }
        }
        return best;
    }

    List<Span> findOccurrences(String word) {
        String needle = word.toLowerCase();
        List<Span> spans = new ArrayList<>();
        for (int i = 0; i < lines.size(); i++) {
            List<String> words = splitWords(lines.get(i));
            for (int j = 0; j < words.size(); j++) {
                if (words.get(j).toLowerCase().equals(needle)) {
                    spans.add(new Span(i + 1, j + 1));
                }
            }
        }
        return spans;
    }

    static String sortedLetters(String word) {
        char[] letters = word.toLowerCase().toCharArray();
        Arrays.sort(letters);
        return new String(letters);
    }

    List<List<String>> anagramGroups() {
        List<String> unique = uniqueWords();
        List<List<String>> groups = new ArrayList<>();
        boolean[] used = new boolean[unique.size()];
        for (int i = 0; i < unique.size(); i++) {
            if (used[i] || unique.get(i).length() < 3) {
                continue;
            }
            List<String> group = new ArrayList<>();
            group.add(unique.get(i));
            for (int j = i + 1; j < unique.size(); j++) {
                if (!used[j] && sortedLetters(unique.get(i)).equals(sortedLetters(unique.get(j)))) {
                    group.add(unique.get(j));
                    used[j] = true;
                }
            }
            if (group.size() > 1) {
                groups.add(group);
            }
        }
        return groups;
    }

    static boolean isPalindrome(String word) {
        String normalized = word.toLowerCase();
        int left = 0;
        int right = normalized.length() - 1;
        while (left < right) {
            if (normalized.charAt(left) != normalized.charAt(right)) {
                return false;
            }
            left++;
            right--;
        }
        return normalized.length() > 2;
    }

    List<String> palindromes() {
        return uniqueWords().stream()
                .filter(Main::isPalindrome)
                .sorted()
                .collect(Collectors.toList());
    }

    Map<String, Long> countByKind() {
        return allWords().stream()
                .collect(Collectors.groupingBy(w -> classify(w).getLabel(), TreeMap::new,
                        Collectors.counting()));
    }

    // ------------------------------------------------------------------
    // Преобразования текста
    // ------------------------------------------------------------------

    int dedupeLines() {
        List<String> result = new ArrayList<>();
        for (String line : lines) {
            boolean duplicate = false;
            for (String kept : result) {
                if (kept.equalsIgnoreCase(line)) {
                    duplicate = true;
                    break;
                }
            }
            if (!duplicate) {
                result.add(line);
            }
        }
        int removed = lines.size() - result.size();
        lines.clear();
        lines.addAll(result);
        return removed;
    }

    int replaceWord(String from, String to) {
        int replaced = 0;
        for (int i = 0; i < lines.size(); i++) {
            String rebuilt = "";
            for (String token : lines.get(i).split(" ")) {
                if (token.equalsIgnoreCase(from)) {
                    token = to;
                    replaced++;
                }
                rebuilt += token + " ";
            }
            lines.set(i, rebuilt.trim());
        }
        return replaced;
    }

    int removeStopWords() {
        int removed = 0;
        for (int i = 0; i < lines.size(); i++) {
            List<String> kept = new ArrayList<>();
            for (String token : lines.get(i).split(" ")) {
                if (stopWords.contains(token.toLowerCase())) {
                    removed++;
                } else {
                    kept.add(token);
                }
            }
            lines.set(i, String.join(" ", kept));
        }
        lines.removeIf(String::isEmpty);
        return removed;
    }

    List<String> wrap(int width) {
        List<String> result = new ArrayList<>();
        String current = "";
        for (String word : allWordsKeepingCase()) {
            if (current.isEmpty()) {
                current = word;
            } else if (current.length() + 1 + word.length() <= width) {
                current += " " + word;
            } else {
                result.add(current);
                current = word;
            }
        }
        if (!current.isEmpty()) {
            result.add(current);
        }
        return result;
    }

    List<String> allWordsKeepingCase() {
        List<String> words = new ArrayList<>();
        for (String line : lines) {
            words.addAll(Arrays.asList(line.split(" ")));
        }
        return words;
    }

    static String caesar(String text, int shift) {
        StringBuilder out = new StringBuilder();
        for (char c : text.toCharArray()) {
            if (c >= 'а' && c <= 'я') {
                out.append((char) ('а' + (c - 'а' + shift % 32 + 32) % 32));
            } else if (c >= 'a' && c <= 'z') {
                out.append((char) ('a' + (c - 'a' + shift % 26 + 26) % 26));
            } else {
                out.append(c);
            }
        }
        return out.toString();
    }

    // ------------------------------------------------------------------
    // Вывод
    // ------------------------------------------------------------------

    void printHeader() {
        System.out.println("=== Анализатор текста ===");
        System.out.println("Команды: add, load, lines, words, freq, find, stats, report, quit");
        System.out.println(repeat('-', 40));
    }

    void printFooter() {
        System.out.println(repeat('-', 40));
        System.out.printf("Команд: %d, ошибок: %d, строк: %d%n", commandCount, errorCount, lines.size());
    }

    static String repeat(char symbol, int count) {
        String result = "";
        for (int i = 0; i < count; i++) {
            result += symbol;
        }
        return result;
    }

    static String padRight(String text, int width) {
        if (text.length() >= width) {
            return text;
        }
        return text + repeat(' ', width - text.length());
    }

    static String padLeft(String text, int width) {
        if (text.length() >= width) {
            return text;
        }
        return repeat(' ', width - text.length()) + text;
    }

    static String percent(int part, int total) {
        if (total == 0) {
            return "0.0%";
        }
        return String.format("%.1f%%", 100.0 * part / total);
    }

    void printLines(List<String> list) {
        if (list.isEmpty()) {
            System.out.println("Документ пуст");
            return;
        }
        for (int i = 0; i < list.size(); i++) {
            System.out.println(padLeft(String.valueOf(i + 1), 3) + ": " + list.get(i));
        }
    }

    void printWords() {
        List<String> words = allWords();
        if (words.isEmpty()) {
            System.out.println("Слов нет");
            return;
        }
        List<String> unique = uniqueWords();
        System.out.println("Слов: " + words.size() + ", уникальных: " + unique.size());
        System.out.println("Самое длинное: " + longestWord());
        System.out.printf("Средняя длина: %.2f%n", averageWordLength());
        System.out.println("Максимум по алфавиту: " + maxOf(unique, ""));
    }

    void printFrequencies(int n) {
        List<Map.Entry<String, Integer>> top = topWords(n);
        if (top.isEmpty()) {
            System.out.println("Частот нет");
            return;
        }
        int max = top.get(0).getValue();
        for (Map.Entry<String, Integer> entry : top) {
            String bar = repeat('#', entry.getValue() * 10 / max);
            System.out.println(padRight(entry.getKey(), 14) + padLeft(String.valueOf(entry.getValue()), 4)
                    + " " + bar);
        }
    }

    void printOccurrences(String word) {
        List<Span> spans = findOccurrences(word);
        if (spans.isEmpty()) {
            System.out.println("«" + word + "» не найдено");
            return;
        }
        System.out.println("«" + word + "»: " + spans.size() + " раз");
        for (Span span : spans) {
            System.out.println("  строка " + span.line() + ", слово " + span.column());
        }
    }

    void printAnagrams() {
        List<List<String>> groups = anagramGroups();
        if (groups.isEmpty()) {
            System.out.println("Анаграмм нет");
            return;
        }
        for (List<String> group : groups) {
            System.out.println(String.join(" = ", group));
        }
    }

    void printPalindromes() {
        List<String> found = palindromes();
        System.out.println(found.isEmpty() ? "Палиндромов нет" : "Палиндромы: " + found);
    }

    void printWrapped(int width) {
        if (width < 5) {
            throw new LimitExceededException("ширина должна быть не меньше 5");
        }
        List<String> wrapped = wrap(width);
        for (String line : wrapped) {
            System.out.println("|" + padRight(line, width) + "|");
        }
        System.out.println("Строк после переноса: " + wrapped.size());
    }

    void printCaesar(int shift) {
        for (String line : lines) {
            System.out.println(caesar(line, shift));
        }
    }

    void printStats() {
        int chars = totalChars();
        System.out.println("Строк: " + lines.size() + ", символов: " + chars);
        System.out.println("Гласных: " + totalVowels() + " (" + percent(totalVowels(), chars) + ")");
        System.out.println("Согласных: " + totalConsonants() + " (" + percent(totalConsonants(), chars) + ")");
        System.out.println("Цифр: " + totalDigits() + " (" + percent(totalDigits(), chars) + ")");
        System.out.println("Предложений: " + countSentences());
    }

    void printHistory() {
        if (history.isEmpty()) {
            System.out.println("История пуста");
            return;
        }
        for (int i = 0; i < history.size(); i++) {
            System.out.println((i + 1) + ") " + history.get(i));
        }
    }

    void printReport() {
        System.out.println("##### ОТЧЁТ #####");
        if (lines.isEmpty()) {
            System.out.println("Данных нет");
            return;
        }
        System.out.println("1. Размер");
        System.out.println("   строк: " + lines.size());
        System.out.println("   символов: " + totalChars());
        System.out.println("   предложений: " + countSentences());
        System.out.println("2. Слова");
        List<String> words = allWords();
        List<String> unique = uniqueWords();
        System.out.println("   всего: " + words.size() + ", уникальных: " + unique.size());
        System.out.println("   самое длинное: " + longestWord());
        System.out.printf("   средняя длина: %.2f%n", averageWordLength());
        System.out.println("3. Виды слов");
        for (Map.Entry<String, Long> entry : countByKind().entrySet()) {
            String mark = entry.getKey() == LONG_LABEL ? "*" : " ";
            System.out.println("  " + mark + padRight(entry.getKey(), 10) + entry.getValue());
        }
        System.out.println("4. Частые слова");
        for (Map.Entry<String, Integer> entry : topWords(3)) {
            System.out.println("   " + entry.getKey() + ": " + entry.getValue());
        }
        System.out.println("5. Буквы");
        System.out.println("   гласных: " + totalVowels());
        System.out.println("   согласных: " + totalConsonants());
        System.out.println("   цифр: " + totalDigits());
        System.out.println("6. Союзы");
        int conjunctions = 0;
        for (String word : words) {
            if (isConjunction(word)) {
                conjunctions++;
            }
        }
        System.out.println("   найдено союза «и»: " + conjunctions);
        System.out.println("7. Особые слова");
        System.out.println("   палиндромы: " + palindromes());
        System.out.println("   анаграммных групп: " + anagramGroups().size());
        System.out.println("##### КОНЕЦ ОТЧЁТА #####");
    }
}

enum WordKind {
    SHORT("Короткое"),
    NORMAL("Обычное"),
    LONG("Длинное");

    private final String label;

    WordKind(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }

    WordKind next() {
        return switch (this) {
            case SHORT -> NORMAL;
            case NORMAL -> LONG;
            case LONG -> SHORT;
        };
    }
}

record Span(int line, int column) {
    Span {
        if (line < 1 || column < 1) {
            throw new IllegalArgumentException("позиция начинается с 1");
        }
    }
}

class TextException extends Exception {
    private static final long serialVersionUID = 1L;

    TextException(String message) {
        super(message);
    }
}

class LimitExceededException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    LimitExceededException(String message) {
        super(message);
    }
}
