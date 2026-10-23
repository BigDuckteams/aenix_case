import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Складской учёт: приход, отгрузка, резервы, цены и отчёты.
 *
 * Программа читает команды из стандартного ввода (одна команда в строке) и хранит товары в памяти.
 * Весь код намеренно собран в одном классе: разбор ввода, проверка, учёт, анализ, преобразования
 * данных и вывод. Класс используется как пример монолита для диагностики и декомпозиции.
 */
public class Main {

    private static final int MAX_QUANTITY = 100000;
    private static final double MAX_PRICE = 1000000.0;
    private static final int MAX_TEXT = 40;
    private static final String FOOD = "Продукты";
    private static final String DISCONTINUED_LABEL = "Снят с продажи";

    private final List<Product> products = new ArrayList<>();
    private final List<Movement> movements = new ArrayList<>();
    private int commandCount;
    private int errorCount;
    private int movementCounter;

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
            try {
                if (!processCommand(line, in)) {
                    break;
                }
            } catch (InventoryException e) {
                errorCount++;
                System.out.println("Ошибка ввода: " + e.getMessage());
            } catch (StockException e) {
                errorCount++;
                System.out.println("Ошибка склада: " + e.getMessage());
            }
        }
    }

    private boolean processCommand(String line, Scanner in) throws InventoryException {
        String[] parts = tokenize(line);
        String command = parts[0].toLowerCase();
        switch (command) {
            case "receive":
                receive(parseProduct(parts, 1));
                break;
            case "batch": {
                int count = parseInt(requireArg(parts, 1, "количество строк"), "количество строк");
                List<Product> batch = readBatch(in, count);
                System.out.printf("Принято позиций: %d из %d%n", receiveAll(batch), count);
                break;
            }
            case "ship":
                ship(requireArg(parts, 1, "артикул"),
                        parseInt(requireArg(parts, 2, "количество"), "количество"));
                break;
            case "reserve":
                reserve(requireArg(parts, 1, "артикул"),
                        parseInt(requireArg(parts, 2, "количество"), "количество"));
                break;
            case "release":
                release(requireArg(parts, 1, "артикул"),
                        parseInt(requireArg(parts, 2, "количество"), "количество"));
                break;
            case "price":
                changePrice(requireArg(parts, 1, "артикул"),
                        parseMoney(requireArg(parts, 2, "цена"), "цена"));
                break;
            case "discontinue":
                discontinue(requireArg(parts, 1, "артикул"));
                break;
            case "remove":
                removeProduct(requireArg(parts, 1, "артикул"));
                break;
            case "list":
                printProducts(parts.length > 1 ? byCategory(normalizeName(parts[1])) : products);
                break;
            case "show":
                printProduct(requireArg(parts, 1, "артикул"));
                break;
            case "low":
                printLowStock(parseInt(requireArg(parts, 1, "порог"), "порог"));
                break;
            case "value":
                printValue();
                break;
            case "categories":
                printCategories();
                break;
            case "merge":
                System.out.println("Объединено позиций: " + mergeSimilar());
                break;
            case "reorder":
                printReorder(parseInt(requireArg(parts, 1, "целевой запас"), "целевой запас"));
                break;
            case "audit":
                printAudit();
                break;
            case "csv":
                printCsvSummary();
                break;
            case "history":
                printMovements();
                break;
            case "report":
                printReport();
                break;
            case "boom":
                throw new IllegalStateException("Принудительное завершение по команде boom");
            case "quit":
            case "exit":
                return false;
            default:
                errorCount++;
                System.out.println("Неизвестная команда: " + parts[0]);
        }
        return true;
    }

    static String[] tokenize(String line) {
        return line.trim().replaceAll("\\s+", " ").split(" ");
    }

    private String requireArg(String[] parts, int index, String what) throws InventoryException {
        if (index >= parts.length) {
            throw new InventoryException("не указан параметр: " + what);
        }
        return parts[index];
    }

    private int parseInt(String token, String what) throws InventoryException {
        try {
            return Integer.parseInt(token);
        } catch (NumberFormatException e) {
            throw new InventoryException("«" + token + "» не число (" + what + ")");
        }
    }

    private double parseMoney(String token, String what) throws InventoryException {
        try {
            return Double.parseDouble(token.replace(',', '.'));
        } catch (NumberFormatException e) {
            throw new InventoryException("«" + token + "» не сумма (" + what + ")");
        }
    }

    private Product parseProduct(String[] parts, int from) throws InventoryException {
        String sku = requireArg(parts, from, "артикул").toUpperCase();
        String name = normalizeName(requireArg(parts, from + 1, "название"));
        String category = normalizeName(requireArg(parts, from + 2, "категория"));
        int quantity = parseInt(requireArg(parts, from + 3, "количество"), "количество");
        double price = parseMoney(requireArg(parts, from + 4, "цена"), "цена");
        return new Product(sku, name, category, quantity, price);
    }

    static String normalizeName(String raw) {
        String name = raw.replace('_', ' ').trim();
        if (name.isEmpty()) {
            return name;
        }
        return Character.toUpperCase(name.charAt(0)) + name.substring(1);
    }

    private List<Product> readBatch(Scanner in, int count) {
        List<Product> batch = new ArrayList<>();
        for (int i = 0; i < count && in.hasNextLine(); i++) {
            String line = in.nextLine().trim();
            try {
                batch.add(parseProduct(tokenize(line), 0));
            } catch (InventoryException e) {
            }
        }
        return batch;
    }

    // ------------------------------------------------------------------
    // Проверка данных
    // ------------------------------------------------------------------

    void validate(Product product) {
        checkSku(product);
        checkName(product);
        checkCategory(product);
        checkQuantity(product);
        checkPrice(product);
    }

    private void checkSku(Product product) {
        String value = product.getSku();
        if (value == null || value.isEmpty()) {
            throw new StockException("пустой артикул");
        }
        if (value.length() > MAX_TEXT) {
            throw new StockException("артикул " + value + ": слишком длинный");
        }
        if (!Character.isLetter(value.charAt(0))) {
            throw new StockException("артикул " + value + ": должен начинаться с буквы");
        }
    }

    private void checkName(Product product) {
        String value = product.getName();
        if (value == null || value.isEmpty()) {
            throw new StockException("артикул " + product.getSku() + ": пустое название");
        }
        if (value.length() > MAX_TEXT) {
            throw new StockException("артикул " + product.getSku() + ": слишком длинное название");
        }
        if (Character.isDigit(value.charAt(0))) {
            throw new StockException("артикул " + product.getSku() + ": название начинается с цифры");
        }
    }

    private void checkCategory(Product product) {
        String value = product.getCategory();
        if (value == null || value.isEmpty()) {
            throw new StockException("артикул " + product.getSku() + ": пустая категория");
        }
        if (value.length() > MAX_TEXT) {
            throw new StockException("артикул " + product.getSku() + ": слишком длинная категория");
        }
        if (Character.isDigit(value.charAt(0))) {
            throw new StockException("артикул " + product.getSku() + ": категория начинается с цифры");
        }
    }

    private void checkQuantity(Product product) {
        if (product.getQuantity() < 0) {
            throw new StockException("артикул " + product.getSku() + ": отрицательное количество");
        }
        if (product.getQuantity() > MAX_QUANTITY) {
            throw new StockException("артикул " + product.getSku() + ": количество больше " + MAX_QUANTITY);
        }
    }

    private void checkPrice(Product product) {
        if (product.getPrice() <= 0) {
            throw new StockException("артикул " + product.getSku() + ": цена должна быть больше нуля");
        }
        if (product.getPrice() > MAX_PRICE) {
            throw new StockException("артикул " + product.getSku() + ": цена больше " + MAX_PRICE);
        }
    }

    // ------------------------------------------------------------------
    // Учёт
    // ------------------------------------------------------------------

    private Product findBySku(String sku) {
        for (Product product : products) {
            if (product.getSku().equalsIgnoreCase(sku)) {
                return product;
            }
        }
        return null;
    }

    private Product require(String sku) {
        Product product = findBySku(sku);
        if (product == null) {
            throw new StockException("артикул " + sku + " не найден");
        }
        return product;
    }

    private void record(String sku, int delta, String reason) {
        movementCounter++;
        movements.add(new Movement(movementCounter, sku, delta, reason));
    }

    void receive(Product incoming) {
        validate(incoming);
        Product existing = findBySku(incoming.getSku());
        if (existing == null) {
            products.add(incoming);
            record(incoming.getSku(), incoming.getQuantity(), "новая позиция");
            System.out.printf("Принят товар %s: %s, %d шт.%n", incoming.getSku(), incoming.getName(),
                    incoming.getQuantity());
            return;
        }
        if (!existing.getName().equals(incoming.getName())) {
            throw new StockException("артикул " + incoming.getSku() + " уже занят товаром «"
                    + existing.getName() + "»");
        }
        existing.addQuantity(incoming.getQuantity());
        existing.setPrice(incoming.getPrice());
        record(existing.getSku(), incoming.getQuantity(), "пополнение");
        System.out.printf("Пополнен товар %s: теперь %d шт.%n", existing.getSku(), existing.getQuantity());
    }

    int receiveAll(List<Product> batch) {
        int accepted = 0;
        for (Product product : batch) {
            try {
                receive(product);
                accepted++;
            } catch (StockException e) {
                errorCount++;
                System.out.println("Пропущена позиция " + product.getSku() + ": " + e.getMessage());
            }
        }
        return accepted;
    }

    void ship(String sku, int quantity) {
        Product product = require(sku);
        if (quantity <= 0) {
            throw new StockException("количество к отгрузке должно быть положительным");
        }
        if (product.getStatus() == StockStatus.DISCONTINUED && quantity > 0 && product.getQuantity() == 0) {
            throw new StockException("товар " + product.getSku() + " снят с продажи и закончился");
        }
        if (quantity > product.available()) {
            throw new StockException("доступно только " + product.available() + " из " + quantity);
        }
        product.addQuantity(-quantity);
        record(product.getSku(), -quantity, "отгрузка");
        System.out.printf("Отгружено %s: %d шт., остаток %d%n", product.getSku(), quantity, product.getQuantity());
    }

    void reserve(String sku, int quantity) {
        Product product = require(sku);
        if (quantity <= 0 || quantity > product.available()) {
            throw new StockException("нельзя зарезервировать " + quantity + " (доступно " + product.available() + ")");
        }
        product.reserve(quantity);
        record(product.getSku(), 0, "резерв " + quantity);
        System.out.printf("Резерв %s: %d шт., свободно %d%n", product.getSku(), quantity, product.available());
    }

    void release(String sku, int quantity) {
        Product product = require(sku);
        if (quantity <= 0 || quantity > product.getReserved()) {
            throw new StockException("нельзя снять резерв " + quantity + " (в резерве " + product.getReserved() + ")");
        }
        product.reserve(-quantity);
        record(product.getSku(), 0, "снят резерв " + quantity);
        System.out.printf("Резерв снят %s: свободно %d%n", product.getSku(), product.available());
    }

    void changePrice(String sku, double price) {
        Product product = require(sku);
        double old = product.getPrice();
        product.setPrice(price);
        checkPrice(product);
        record(product.getSku(), 0, "цена " + format(old) + " -> " + format(price));
        System.out.println("Цена " + product.getSku() + ": " + format(old) + " -> " + format(price));
    }

    void discontinue(String sku) {
        Product product = require(sku);
        product.setStatus(StockStatus.DISCONTINUED);
        record(product.getSku(), 0, "снят с продажи");
        System.out.println("Снят с продажи: " + product.getSku());
    }

    void removeProduct(String sku) {
        for (int i = 0; i < products.size(); i++) {
            if (products.get(i).getSku().equalsIgnoreCase(sku)) {
                Product removed = products.remove(i);
                record(removed.getSku(), -removed.getQuantity(), "удалён");
                System.out.println("Удалён " + removed.getSku() + " (" + removed.getName() + ")");
                return;
            }
        }
        throw new StockException("артикул " + sku + " не найден");
    }

    List<Product> byCategory(String category) {
        List<Product> result = new ArrayList<>();
        for (Product product : products) {
            if (product.getCategory().equals(category)) {
                result.add(product);
            }
        }
        return result;
    }

    // ------------------------------------------------------------------
    // Анализ
    // ------------------------------------------------------------------

    int totalQuantity() {
        int total = 0;
        for (Product product : products) {
            total += product.getQuantity();
        }
        return total;
    }

    double totalValue() {
        double total = 0;
        for (Product product : products) {
            total += product.value();
        }
        return total;
    }

    Map<String, Integer> quantityByCategory() {
        Map<String, Integer> result = new TreeMap<>();
        for (Product product : products) {
            result.merge(product.getCategory(), product.getQuantity(), Integer::sum);
        }
        return result;
    }

    Map<String, Double> valueByCategory() {
        Map<String, Double> result = new TreeMap<>();
        for (Product product : products) {
            result.merge(product.getCategory(), product.value(), Double::sum);
        }
        return result;
    }

    List<String> categories() {
        List<String> result = new ArrayList<>();
        for (Product product : products) {
            if (!result.contains(product.getCategory())) {
                result.add(product.getCategory());
            }
        }
        Collections.sort(result);
        return result;
    }

    List<Product> lowStock(int threshold) {
        return products.stream()
                .filter(p -> p.getStatus() == StockStatus.ACTIVE)
                .filter(p -> p.available() <= threshold)
                .sorted(Comparator.comparingInt(Product::available).thenComparing(Product::getSku))
                .collect(Collectors.toList());
    }

    Product mostValuable() {
        Product best = null;
        for (Product product : products) {
            if (best == null || product.value() > best.value()) {
                best = product;
            }
        }
        return best;
    }

    double averagePrice() {
        if (products.isEmpty()) {
            return 0;
        }
        double sum = 0;
        for (Product product : products) {
            sum += product.getPrice();
        }
        return sum / products.size();
    }

    List<CategoryTotal> categoryTotals() {
        Map<String, Integer> quantities = quantityByCategory();
        Map<String, Double> values = valueByCategory();
        List<CategoryTotal> totals = new ArrayList<>();
        for (Map.Entry<String, Double> entry : values.entrySet()) {
            totals.add(new CategoryTotal(entry.getKey(), quantities.get(entry.getKey()), entry.getValue()));
        }
        return topN(totals, Comparator.comparingDouble(CategoryTotal::value).reversed()
                .thenComparing(CategoryTotal::category), 100);
    }

    static <T> List<T> topN(List<T> items, Comparator<? super T> order, int n) {
        List<T> sorted = new ArrayList<>(items);
        sorted.sort(order);
        return new ArrayList<>(sorted.subList(0, Math.min(Math.max(n, 0), sorted.size())));
    }

    List<String> audit() {
        List<String> problems = new ArrayList<>();
        for (Product product : products) {
            if (product.getReserved() > product.getQuantity()) {
                problems.add(product.getSku() + ": резерв больше остатка");
            }
            if (product.getCategory() == FOOD && product.getQuantity() > 500) {
                problems.add(product.getSku() + ": продукты с большим запасом, проверьте срок годности");
            }
            if (product.getStatus() == StockStatus.DISCONTINUED && product.getQuantity() > 0) {
                problems.add(product.getSku() + ": снят с продажи, но остаток " + product.getQuantity());
            }
        }
        return problems;
    }

    // ------------------------------------------------------------------
    // Преобразования данных
    // ------------------------------------------------------------------

    int mergeSimilar() {
        List<Product> merged = new ArrayList<>();
        for (Product candidate : products) {
            boolean found = false;
            for (Product existing : merged) {
                if (existing.getName().equals(candidate.getName())
                        && existing.getCategory().equals(candidate.getCategory())
                        && existing.getStatus() == candidate.getStatus()) {
                    existing.addQuantity(candidate.getQuantity());
                    existing.setPrice(Math.min(existing.getPrice(), candidate.getPrice()));
                    record(existing.getSku(), candidate.getQuantity(), "объединено с " + candidate.getSku());
                    found = true;
                    break;
                }
            }
            if (!found) {
                merged.add(candidate.copy());
            }
        }
        int removed = products.size() - merged.size();
        products.clear();
        products.addAll(merged);
        return removed;
    }

    String buildCsv() {
        String csv = "артикул;название;категория;остаток;цена;статус\n";
        for (Product product : products) {
            csv += product.getSku() + ";" + product.getName() + ";" + product.getCategory() + ";"
                    + product.getQuantity() + ";" + format(product.getPrice()) + ";"
                    + product.getStatus().getLabel() + "\n";
        }
        return csv;
    }

    List<String> reorderPlan(int target) {
        List<String> plan = new ArrayList<>();
        for (Product product : products) {
            if (product.getStatus() == StockStatus.ACTIVE && product.available() < target) {
                int need = target - product.available();
                plan.add(product.getSku() + " " + product.getName() + ": заказать " + need
                        + " шт. на " + format(need * product.getPrice()));
            }
        }
        return plan;
    }

    // ------------------------------------------------------------------
    // Вывод
    // ------------------------------------------------------------------

    void printHeader() {
        System.out.println("=== Складской учёт ===");
        System.out.println("Команды: receive, batch, ship, reserve, release, price, list, value, report, quit");
        System.out.println(repeat('-', 40));
    }

    void printFooter() {
        System.out.println(repeat('-', 40));
        System.out.printf("Команд: %d, ошибок: %d, позиций: %d%n", commandCount, errorCount, products.size());
    }

    static String repeat(char symbol, int count) {
        String result = "";
        for (int i = 0; i < count; i++) {
            result += symbol;
        }
        return result;
    }

    static String format(double value) {
        return String.format("%.2f", value);
    }

    static String padRight(String text, int width) {
        if (text.length() >= width) {
            return text;
        }
        return text + repeat(' ', width - text.length());
    }

    void printProducts(List<Product> list) {
        if (list.isEmpty()) {
            System.out.println("Товаров нет");
            return;
        }
        System.out.printf("%-8s %-16s %-12s %6s %6s %10s %s%n", "Артикул", "Название", "Категория", "Остаток",
                "Резерв", "Цена", "Статус");
        for (Product product : list) {
            String mark = product.getStatus().getLabel() == DISCONTINUED_LABEL ? "x" : " ";
            System.out.printf("%-8s %-16s %-12s %6d %6d %10.2f %s%s%n", product.getSku(), product.getName(),
                    product.getCategory(), product.getQuantity(), product.getReserved(), product.getPrice(), mark,
                    product.getStatus().getLabel());
        }
        System.out.println("Всего позиций: " + list.size());
    }

    void printProduct(String sku) {
        Product product = require(sku);
        System.out.println(product.describe());
        System.out.println(product.shortInfo());
    }

    void printLowStock(int threshold) {
        List<Product> low = lowStock(threshold);
        if (low.isEmpty()) {
            System.out.println("Всё в наличии: порог " + threshold);
            return;
        }
        for (Product product : low) {
            System.out.println(product.getSku() + " " + product.getName() + ": свободно " + product.available());
        }
    }

    void printValue() {
        if (products.isEmpty()) {
            System.out.println("Склад пуст");
            return;
        }
        System.out.println("Общая стоимость: " + format(totalValue()));
        System.out.println("Единиц на складе: " + totalQuantity());
        for (CategoryTotal item : categoryTotals()) {
            System.out.printf("  %s: %d шт., %.2f%n", item.category(), item.quantity(), item.value());
        }
    }

    void printCategories() {
        List<String> names = categories();
        if (names.isEmpty()) {
            System.out.println("Категорий нет");
            return;
        }
        String joined = "";
        for (int i = 0; i < names.size(); i++) {
            if (i > 0) {
                joined += ", ";
            }
            joined += names.get(i);
        }
        System.out.println("Категорий: " + names.size());
        System.out.println(joined);
    }

    void printReorder(int target) {
        List<String> plan = reorderPlan(target);
        if (plan.isEmpty()) {
            System.out.println("Пополнение не требуется");
            return;
        }
        for (String line : plan) {
            System.out.println(line);
        }
    }

    void printAudit() {
        List<String> problems = audit();
        if (problems.isEmpty()) {
            System.out.println("Аудит: замечаний нет");
            return;
        }
        for (String problem : problems) {
            System.out.println("Замечание: " + problem);
        }
    }

    void printCsvSummary() {
        String csv = buildCsv();
        String[] rows = csv.split("\n");
        System.out.println("CSV: строк " + rows.length + ", символов " + csv.length());
        for (int i = 0; i < rows.length && i < 4; i++) {
            System.out.println(rows[i]);
        }
    }

    void printMovements() {
        if (movements.isEmpty()) {
            System.out.println("Движений нет");
            return;
        }
        for (Movement movement : movements) {
            System.out.println(movement.describe());
        }
    }

    void printReport() {
        System.out.println("##### ОТЧЁТ ПО СКЛАДУ #####");
        if (products.isEmpty()) {
            System.out.println("Данных нет");
            return;
        }
        System.out.println("1. Общие показатели");
        System.out.println("   позиций: " + products.size());
        System.out.println("   единиц: " + totalQuantity());
        System.out.println("   стоимость: " + format(totalValue()));
        System.out.println("   средняя цена: " + format(averagePrice()));
        System.out.println("2. По категориям");
        for (CategoryTotal item : categoryTotals()) {
            System.out.println("   " + padRight(item.category(), 14) + padRight(String.valueOf(item.quantity()), 8)
                    + format(item.value()));
        }
        System.out.println("3. Самая дорогая позиция");
        Product best = mostValuable();
        System.out.println("   " + best.getSku() + " " + best.getName() + ": " + format(best.value()));
        System.out.println("4. Мало на складе (до 10)");
        List<Product> low = lowStock(10);
        if (low.isEmpty()) {
            System.out.println("   нет");
        } else {
            for (Product product : low) {
                System.out.println("   " + product.getSku() + ": " + product.available());
            }
        }
        System.out.println("5. Снятые с продажи");
        int discontinued = 0;
        for (Product product : products) {
            if (product.getStatus() == StockStatus.DISCONTINUED) {
                System.out.println("   " + product.getSku() + " " + product.getName());
                discontinued++;
            }
        }
        if (discontinued == 0) {
            System.out.println("   нет");
        }
        System.out.println("6. Аудит");
        List<String> problems = audit();
        System.out.println("   замечаний: " + problems.size());
        for (String problem : problems) {
            System.out.println("   - " + problem);
        }
        System.out.println("7. Движения");
        System.out.println("   записей: " + movements.size());
        int received = 0;
        int shipped = 0;
        for (Movement movement : movements) {
            if (movement.delta() > 0) {
                received += movement.delta();
            } else if (movement.delta() < 0) {
                shipped -= movement.delta();
            }
        }
        System.out.println("   принято: " + received + ", отгружено: " + shipped);
        System.out.println("##### КОНЕЦ ОТЧЁТА #####");
    }
}

interface Describable {
    String describe();

    default String shortInfo() {
        return describe().toUpperCase();
    }
}

enum StockStatus {
    ACTIVE("В продаже"),
    DISCONTINUED("Снят с продажи");

    private final String label;

    StockStatus(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }
}

class Product implements Describable {
    private final String sku;
    private final String name;
    private final String category;
    private int quantity;
    private int reserved;
    private double price;
    private StockStatus status = StockStatus.ACTIVE;

    Product(String sku, String name, String category, int quantity, double price) {
        this.sku = sku;
        this.name = name;
        this.category = category;
        this.quantity = quantity;
        this.price = price;
    }

    String getSku() {
        return sku;
    }

    String getName() {
        return name;
    }

    String getCategory() {
        return category;
    }

    int getQuantity() {
        return quantity;
    }

    int getReserved() {
        return reserved;
    }

    double getPrice() {
        return price;
    }

    StockStatus getStatus() {
        return status;
    }

    void setStatus(StockStatus status) {
        this.status = status;
    }

    void setPrice(double price) {
        this.price = price;
    }

    void addQuantity(int delta) {
        this.quantity += delta;
    }

    void reserve(int delta) {
        this.reserved += delta;
    }

    int available() {
        return quantity - reserved;
    }

    double value() {
        return quantity * price;
    }

    Product copy() {
        Product clone = new Product(sku, name, category, quantity, price);
        clone.reserved = reserved;
        clone.status = status;
        return clone;
    }

    @Override
    public String describe() {
        return "Товар " + sku + ": " + name + " (" + category + "), " + quantity + " шт. по "
                + Main.format(price) + " — " + status.getLabel();
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof Product)) {
            return false;
        }
        return sku.equals(((Product) other).sku);
    }

    @Override
    public int hashCode() {
        return sku.hashCode();
    }
}

record Movement(int number, String sku, int delta, String reason) {
    String describe() {
        String sign = delta > 0 ? "+" : "";
        return "#" + number + " " + sku + " " + sign + delta + " (" + reason + ")";
    }
}

record CategoryTotal(String category, int quantity, double value) {
}

class InventoryException extends Exception {
    private static final long serialVersionUID = 1L;

    InventoryException(String message) {
        super(message);
    }
}

class StockException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    StockException(String message) {
        super(message);
    }
}
