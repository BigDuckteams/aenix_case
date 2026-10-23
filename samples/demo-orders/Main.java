import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Демонстрационный монолит: учёт заказов небольшого магазина.
 *
 * Программа читает команды из стандартного ввода (одна команда в строке), хранит заказы
 * в памяти и печатает результаты. Весь код намеренно собран в одном классе: разбор ввода,
 * проверка, анализ, преобразования данных и вывод. Класс используется как основной пример
 * для диагностики, оптимизации и декомпозиции.
 */
public class Main {

    private static final int MAX_QUANTITY = 1000;
    private static final double MAX_PRICE = 100000.0;
    private static final int MAX_NAME_LENGTH = 30;
    private static final String VIP_CUSTOMER = "Иванов";
    private static final String CANCELLED_LABEL = "Отменён";

    private final List<Order> orders = new ArrayList<>();
    private final List<String> history = new ArrayList<>();
    private int commandCount;
    private int errorCount;
    private double discountPercent;

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
                boolean goOn = processCommand(line, in);
                if (!goOn) {
                    break;
                }
            } catch (OrderParseException e) {
                errorCount++;
                System.out.println("Ошибка разбора: " + e.getMessage());
            } catch (OrderValidationException e) {
                errorCount++;
                System.out.println("Ошибка проверки: " + e.getMessage());
            }
        }
    }

    private boolean processCommand(String line, Scanner in) throws OrderParseException {
        String[] parts = tokenize(line);
        String command = parts[0].toLowerCase();
        switch (command) {
            case "add":
                addOrder(parseOrder(parts, 1));
                break;
            case "batch": {
                int count = parseInt(requireArg(parts, 1, "количество строк"), "количество строк");
                List<Order> batch = readBatch(in, count);
                int accepted = processOrders(batch);
                System.out.printf("Принято заказов: %d из %d%n", accepted, count);
                break;
            }
            case "pay":
                changeStatus(parseInt(requireArg(parts, 1, "номер заказа"), "номер заказа"),
                        OrderStatus.PAID);
                break;
            case "ship":
                changeStatus(parseInt(requireArg(parts, 1, "номер заказа"), "номер заказа"),
                        OrderStatus.SHIPPED);
                break;
            case "cancel":
                changeStatus(parseInt(requireArg(parts, 1, "номер заказа"), "номер заказа"),
                        OrderStatus.CANCELLED);
                break;
            case "remove":
                removeOrder(parseInt(requireArg(parts, 1, "номер заказа"), "номер заказа"));
                break;
            case "purge":
                System.out.println("Удалено отменённых заказов: " + purgeCancelled());
                break;
            case "list":
                printOrders(orders);
                break;
            case "show":
                showOrder(parseInt(requireArg(parts, 1, "номер заказа"), "номер заказа"));
                break;
            case "find":
                printOrders(findByCustomer(requireArg(parts, 1, "часть имени")));
                break;
            case "stats":
                printStats();
                break;
            case "top":
                printTopCustomers(parseInt(requireArg(parts, 1, "количество"), "количество"));
                break;
            case "customers":
                printCustomers();
                break;
            case "merge":
                System.out.println("Объединено заказов: " + mergeDuplicates());
                break;
            case "csv":
                printCsvSummary();
                break;
            case "discount":
                applyDiscount(parseMoney(requireArg(parts, 1, "процент"), "процент"));
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
                System.out.println("Неизвестная команда: " + parts[0]);
        }
        return true;
    }

    static String[] tokenize(String line) {
        String normalized = line.trim().replaceAll("\\s+", " ");
        return normalized.split(" ");
    }

    private String requireArg(String[] parts, int index, String what) throws OrderParseException {
        if (index >= parts.length) {
            throw new OrderParseException("не указан параметр: " + what);
        }
        return parts[index];
    }

    private int parseInt(String token, String what) throws OrderParseException {
        try {
            return Integer.parseInt(token);
        } catch (NumberFormatException e) {
            throw new OrderParseException("«" + token + "» не число (" + what + ")");
        }
    }

    private double parseMoney(String token, String what) throws OrderParseException {
        try {
            return Double.parseDouble(token.replace(',', '.'));
        } catch (NumberFormatException e) {
            throw new OrderParseException("«" + token + "» не сумма (" + what + ")");
        }
    }

    private Order parseOrder(String[] parts, int from) throws OrderParseException {
        int id = parseInt(requireArg(parts, from, "номер заказа"), "номер заказа");
        String customer = requireArg(parts, from + 1, "клиент");
        String product = requireArg(parts, from + 2, "товар");
        int quantity = parseInt(requireArg(parts, from + 3, "количество"), "количество");
        double price = parseMoney(requireArg(parts, from + 4, "цена"), "цена");
        return new Order(id, normalizeName(customer), normalizeName(product), quantity, price);
    }

    static String normalizeName(String raw) {
        String name = raw.replace('_', ' ').trim();
        if (name.isEmpty()) {
            return name;
        }
        return Character.toUpperCase(name.charAt(0)) + name.substring(1);
    }

    private List<Order> readBatch(Scanner in, int count) {
        List<Order> batch = new ArrayList<>();
        for (int i = 0; i < count && in.hasNextLine(); i++) {
            String line = in.nextLine().trim();
            try {
                batch.add(parseOrder(tokenize(line), 0));
            } catch (OrderParseException e) {
            }
        }
        return batch;
    }

    // ------------------------------------------------------------------
    // Проверка данных
    // ------------------------------------------------------------------

    void validate(Order order) {
        checkId(order);
        checkCustomer(order);
        checkProduct(order);
        checkQuantity(order);
        checkPrice(order);
    }

    private void checkId(Order order) {
        if (order.getId() <= 0) {
            throw new OrderValidationException("номер заказа должен быть положительным: " + order.getId());
        }
    }

    private void checkCustomer(Order order) {
        String value = order.getCustomer();
        if (value == null || value.isEmpty()) {
            throw new OrderValidationException("заказ " + order.getId() + ": пустое имя клиента");
        }
        if (value.length() > MAX_NAME_LENGTH) {
            throw new OrderValidationException("заказ " + order.getId() + ": слишком длинное имя клиента");
        }
        if (Character.isDigit(value.charAt(0))) {
            throw new OrderValidationException("заказ " + order.getId() + ": имя клиента начинается с цифры");
        }
    }

    private void checkProduct(Order order) {
        String value = order.getProduct();
        if (value == null || value.isEmpty()) {
            throw new OrderValidationException("заказ " + order.getId() + ": пустое название товара");
        }
        if (value.length() > MAX_NAME_LENGTH) {
            throw new OrderValidationException("заказ " + order.getId() + ": слишком длинное название товара");
        }
        if (Character.isDigit(value.charAt(0))) {
            throw new OrderValidationException("заказ " + order.getId() + ": название товара начинается с цифры");
        }
    }

    private void checkQuantity(Order order) {
        if (order.getQuantity() <= 0) {
            throw new OrderValidationException("заказ " + order.getId() + ": количество должно быть больше нуля");
        }
        if (order.getQuantity() > MAX_QUANTITY) {
            throw new OrderValidationException("заказ " + order.getId() + ": количество больше " + MAX_QUANTITY);
        }
    }

    private void checkPrice(Order order) {
        if (order.getUnitPrice() <= 0) {
            throw new OrderValidationException("заказ " + order.getId() + ": цена должна быть больше нуля");
        }
        if (order.getUnitPrice() > MAX_PRICE) {
            throw new OrderValidationException("заказ " + order.getId() + ": цена больше " + MAX_PRICE);
        }
    }

    // ------------------------------------------------------------------
    // Хранение и изменение заказов
    // ------------------------------------------------------------------

    private Order findOrderById(int id) {
        for (Order order : orders) {
            if (order.getId() == id) {
                return order;
            }
        }
        return null;
    }

    void addOrder(Order order) {
        validate(order);
        if (findOrderById(order.getId()) != null) {
            throw new OrderValidationException("заказ " + order.getId() + " уже существует");
        }
        orders.add(order);
        System.out.printf("Добавлен заказ %d: %s, %s x%d%n", order.getId(), order.getCustomer(),
                order.getProduct(), order.getQuantity());
    }

    int processOrders(List<Order> batch) {
        int accepted = 0;
        for (Order order : batch) {
            if (order.getQuantity() > 0) {
                try {
                    addOrder(order);
                    accepted++;
                } catch (OrderValidationException e) {
                    errorCount++;
                    System.out.println("Пропущен заказ " + order.getId() + ": " + e.getMessage());
                }
            } else {
                errorCount++;
                System.out.println("Пропущен заказ " + order.getId() + ": нулевое количество");
            }
        }
        return accepted;
    }

    void changeStatus(int id, OrderStatus target) {
        Order order = findOrderById(id);
        if (order == null) {
            throw new OrderValidationException("заказ " + id + " не найден");
        }
        OrderStatus current = order.getStatus();
        if (!current.canMoveTo(target)) {
            throw new OrderValidationException("заказ " + id + ": нельзя перевести из «"
                    + current.getLabel() + "» в «" + target.getLabel() + "»");
        }
        order.setStatus(target);
        System.out.printf("Заказ %d: %s -> %s%n", id, current.getLabel(), target.getLabel());
    }

    void removeOrder(int id) {
        for (int i = 0; i < orders.size(); i++) {
            if (orders.get(i).getId() == id) {
                Order removed = orders.remove(i);
                System.out.println("Удалён заказ " + removed.getId() + " (" + removed.getCustomer() + ")");
                return;
            }
        }
        throw new OrderValidationException("заказ " + id + " не найден");
    }

    int purgeCancelled() {
        int before = orders.size();
        orders.removeIf(o -> o.getStatus() == OrderStatus.CANCELLED);
        return before - orders.size();
    }

    List<Order> findByCustomer(String part) {
        String needle = part.toLowerCase();
        List<Order> result = new ArrayList<>();
        for (Order order : orders) {
            if (order.getCustomer().toLowerCase().contains(needle)) {
                result.add(order);
            }
        }
        return result;
    }

    private void showOrder(int id) {
        Order order = findOrderById(id);
        if (order == null) {
            throw new OrderValidationException("заказ " + id + " не найден");
        }
        System.out.println(order.describe());
        System.out.println(order.shortInfo());
    }

    // ------------------------------------------------------------------
    // Анализ
    // ------------------------------------------------------------------

    double totalAmount() {
        double sum = 0;
        for (Order order : orders) {
            if (order.getStatus() != OrderStatus.CANCELLED) {
                sum += order.getTotal();
            }
        }
        return sum;
    }

    double averageAmount() {
        int count = 0;
        double sum = 0;
        for (Order order : orders) {
            if (order.getStatus() != OrderStatus.CANCELLED) {
                sum += order.getTotal();
                count++;
            }
        }
        if (count == 0) {
            return 0;
        }
        return sum / count;
    }

    double medianAmount() {
        List<Double> totals = new ArrayList<>();
        for (Order order : orders) {
            if (order.getStatus() != OrderStatus.CANCELLED) {
                totals.add(order.getTotal());
            }
        }
        if (totals.isEmpty()) {
            return 0;
        }
        Collections.sort(totals);
        int middle = totals.size() / 2;
        if (totals.size() % 2 == 1) {
            return totals.get(middle);
        }
        return (totals.get(middle - 1) + totals.get(middle)) / 2;
    }

    double percentile(double percent) {
        List<Double> totals = new ArrayList<>();
        for (Order order : orders) {
            if (order.getStatus() != OrderStatus.CANCELLED) {
                totals.add(order.getTotal());
            }
        }
        if (totals.isEmpty()) {
            return 0;
        }
        Collections.sort(totals);
        int index = (int) Math.ceil(percent / 100.0 * totals.size()) - 1;
        index = Math.max(0, Math.min(index, totals.size() - 1));
        return totals.get(index);
    }

    Order maxOrder() {
        Order best = null;
        for (Order order : orders) {
            if (best == null || order.getTotal() > best.getTotal()) {
                best = order;
            }
        }
        return best;
    }

    Order minOrder() {
        Order best = null;
        for (Order order : orders) {
            if (best == null || order.getTotal() < best.getTotal()) {
                best = order;
            }
        }
        return best;
    }

    Map<OrderStatus, Integer> statusHistogram() {
        Map<OrderStatus, Integer> histogram = new EnumMap<>(OrderStatus.class);
        for (OrderStatus status : OrderStatus.values()) {
            histogram.put(status, 0);
        }
        for (Order order : orders) {
            histogram.put(order.getStatus(), histogram.get(order.getStatus()) + 1);
        }
        return histogram;
    }

    double totalForCustomer(String customer) {
        double sum = 0;
        for (Order order : orders) {
            if (order.getCustomer().equals(customer) && order.getStatus() != OrderStatus.CANCELLED) {
                sum += order.getTotal();
            }
        }
        return sum;
    }

    double totalForProduct(String product) {
        double sum = 0;
        for (Order order : orders) {
            if (order.getProduct().equals(product) && order.getStatus() != OrderStatus.CANCELLED) {
                sum += order.getTotal();
            }
        }
        return sum;
    }

    List<CustomerTotal> topCustomers(int n) {
        Map<String, Integer> counts = new TreeMap<>();
        Map<String, Double> sums = new TreeMap<>();
        for (Order order : orders) {
            if (order.getStatus() == OrderStatus.CANCELLED) {
                continue;
            }
            String customer = order.getCustomer();
            counts.merge(customer, 1, Integer::sum);
            sums.merge(customer, order.getTotal(), Double::sum);
        }
        List<CustomerTotal> totals = new ArrayList<>();
        for (Map.Entry<String, Double> entry : sums.entrySet()) {
            totals.add(new CustomerTotal(entry.getKey(), counts.get(entry.getKey()), entry.getValue()));
        }
        Comparator<CustomerTotal> byTotal = Comparator.comparingDouble(CustomerTotal::total).reversed();
        return topN(totals, byTotal.thenComparing(CustomerTotal::customer), n);
    }

    static <T> List<T> topN(List<T> items, Comparator<? super T> order, int n) {
        List<T> sorted = new ArrayList<>(items);
        sorted.sort(order);
        return new ArrayList<>(sorted.subList(0, Math.min(Math.max(n, 0), sorted.size())));
    }

    List<String> distinctCustomers() {
        List<String> result = new ArrayList<>();
        for (Order order : orders) {
            if (!result.contains(order.getCustomer())) {
                result.add(order.getCustomer());
            }
        }
        return result;
    }

    List<Integer> findAnomalies() {
        double average = averageAmount();
        List<Integer> ids = new ArrayList<>();
        for (Order order : orders) {
            if (average > 0 && order.getTotal() > 3 * average) {
                ids.add(order.getId());
            }
        }
        return ids;
    }

    Map<String, Long> countByStatusLabel() {
        return orders.stream()
                .collect(Collectors.groupingBy(o -> o.getStatus().getLabel(), TreeMap::new,
                        Collectors.counting()));
    }

    double streamTotalForCustomer(String customer) {
        return orders.stream()
                .filter(o -> o.getCustomer().equals(customer))
                .filter(o -> o.getStatus() != OrderStatus.CANCELLED)
                .mapToDouble(Order::getTotal)
                .sum();
    }

    List<String> expensiveProducts(double threshold) {
        return orders.stream()
                .filter(o -> o.getUnitPrice() >= threshold)
                .map(Order::getProduct)
                .distinct()
                .sorted()
                .collect(Collectors.toList());
    }

    int countLargeOrders(int minQuantity) {
        int count = 0;
        for (Order order : orders) {
            if (order.getQuantity() >= minQuantity) {
                count++;
            }
        }
        return count;
    }

    // ------------------------------------------------------------------
    // Преобразования данных
    // ------------------------------------------------------------------

    int mergeDuplicates() {
        List<Order> merged = new ArrayList<>();
        for (Order candidate : orders) {
            boolean found = false;
            for (Order existing : merged) {
                if (existing.getCustomer().equals(candidate.getCustomer())
                        && existing.getProduct().equals(candidate.getProduct())
                        && existing.getStatus() == candidate.getStatus()) {
                    existing.addQuantity(candidate.getQuantity());
                    found = true;
                    break;
                }
            }
            if (!found) {
                merged.add(candidate.copy());
            }
        }
        int removed = orders.size() - merged.size();
        orders.clear();
        orders.addAll(merged);
        return removed;
    }

    String buildCsv() {
        String csv = "id;клиент;товар;количество;сумма;статус\n";
        for (Order order : orders) {
            csv += order.getId() + ";" + order.getCustomer() + ";" + order.getProduct() + ";"
                    + order.getQuantity() + ";" + formatAmount(order.getTotal()) + ";"
                    + order.getStatus().getLabel() + "\n";
        }
        return csv;
    }

    void applyDiscount(double percent) {
        if (percent < 0 || percent > 50) {
            throw new OrderValidationException("скидка должна быть от 0 до 50 процентов");
        }
        discountPercent = percent;
        int changed = 0;
        for (Order order : orders) {
            if (order.getStatus() == OrderStatus.NEW) {
                double rate = discountFor(order);
                order.setUnitPrice(roundMoney(order.getBasePrice() * (1 - rate / 100)));
                changed++;
            }
        }
        System.out.printf("Скидка %.1f%% применена к заказам: %d%n", percent, changed);
    }

    private double discountFor(Order order) {
        double tier = switch (order.getQuantity() / 10) {
            case 0 -> 0.0;
            case 1, 2 -> 2.5;
            default -> {
                double extra = order.getQuantity() >= 100 ? 5.0 : 4.0;
                yield extra;
            }
        };
        if (order.getCustomer() == VIP_CUSTOMER) {
            tier += 10;
        }
        return Math.min(discountPercent + tier, 60.0);
    }

    static double roundMoney(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    // ------------------------------------------------------------------
    // Вывод
    // ------------------------------------------------------------------

    void printHeader() {
        System.out.println("=== Система учёта заказов ===");
        System.out.println("Команды: add, batch, pay, ship, cancel, remove, list, stats, report, quit");
        System.out.println(repeat('-', 40));
    }

    void printFooter() {
        System.out.println(repeat('-', 40));
        System.out.printf("Команд: %d, ошибок: %d, заказов: %d%n", commandCount, errorCount, orders.size());
    }

    static String repeat(char symbol, int count) {
        String result = "";
        for (int i = 0; i < count; i++) {
            result += symbol;
        }
        return result;
    }

    static String formatAmount(double value) {
        return String.format("%.2f", value);
    }

    static String padRight(String text, int width) {
        if (text.length() >= width) {
            return text;
        }
        return text + repeat(' ', width - text.length());
    }

    void printOrders(List<Order> list) {
        if (list.isEmpty()) {
            System.out.println("Заказов нет");
            return;
        }
        System.out.printf("%-5s %-12s %-14s %5s %10s  %s%n", "№", "Клиент", "Товар", "Кол.", "Сумма",
                "Статус");
        for (Order order : list) {
            String mark = " ";
            if (order.getStatus().getLabel() == CANCELLED_LABEL) {
                mark = "x";
            }
            System.out.printf("%-5d %-12s %-14s %5d %10.2f %s%s%n", order.getId(), order.getCustomer(),
                    order.getProduct(), order.getQuantity(), order.getTotal(), mark,
                    order.getStatus().getLabel());
        }
        System.out.println("Всего строк: " + list.size());
    }

    void printStats() {
        if (orders.isEmpty()) {
            System.out.println("Статистика: заказов нет");
            return;
        }
        System.out.println("Заказов: " + orders.size());
        System.out.println("Сумма (без отменённых): " + formatAmount(totalAmount()));
        System.out.println("Среднее: " + formatAmount(averageAmount()));
        System.out.println("Медиана: " + formatAmount(medianAmount()));
        Order max = maxOrder();
        Order min = minOrder();
        System.out.println("Максимум: заказ " + max.getId() + " на " + formatAmount(max.getTotal()));
        System.out.println("Минимум: заказ " + min.getId() + " на " + formatAmount(min.getTotal()));
        System.out.println("90-й перцентиль: " + formatAmount(percentile(90)));
        printStatusBars();
    }

    void printStatusBars() {
        Map<OrderStatus, Integer> histogram = statusHistogram();
        int max = 1;
        for (int value : histogram.values()) {
            if (value > max) {
                max = value;
            }
        }
        for (Map.Entry<OrderStatus, Integer> entry : histogram.entrySet()) {
            String label = padRight(entry.getKey().getLabel(), 10);
            String bar = padRight(bar(entry.getValue(), max), 12);
            System.out.println("  " + label + bar + entry.getValue());
        }
    }

    static String bar(int value, int max) {
        int length = value * 10 / max;
        return repeat('#', length);
    }

    void printTopCustomers(int n) {
        List<CustomerTotal> top = topCustomers(n);
        if (top.isEmpty()) {
            System.out.println("Клиентов нет");
            return;
        }
        int place = 1;
        for (CustomerTotal item : top) {
            System.out.printf("%d. %s: %d зак., %.2f (в среднем %.2f)%n", place, item.customer(),
                    item.orders(), item.total(), item.average());
            place++;
        }
    }

    void printCustomers() {
        List<String> names = distinctCustomers();
        if (names.isEmpty()) {
            System.out.println("Клиентов нет");
            return;
        }
        String joined = "";
        for (int i = 0; i < names.size(); i++) {
            if (i > 0) {
                joined += ", ";
            }
            joined += names.get(i);
        }
        System.out.println("Клиентов: " + names.size());
        System.out.println(joined);
    }

    void printCsvSummary() {
        String csv = buildCsv();
        String[] rows = csv.split("\n");
        System.out.println("CSV: строк " + rows.length + ", символов " + csv.length());
        for (int i = 0; i < rows.length && i < 4; i++) {
            System.out.println(rows[i]);
        }
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

    void printByCustomer(String customer) {
        double sum = 0;
        int count = 0;
        for (Order order : orders) {
            if (order.getCustomer().equals(customer)) {
                System.out.printf("  заказ %d: %s x%d = %.2f%n", order.getId(), order.getProduct(),
                        order.getQuantity(), order.getTotal());
                sum += order.getTotal();
                count++;
            }
        }
        System.out.printf("  итого по клиенту %s: %d зак., %.2f%n", customer, count, sum);
    }

    void printByProduct(String product) {
        double sum = 0;
        int count = 0;
        for (Order order : orders) {
            if (order.getProduct().equals(product)) {
                System.out.printf("  заказ %d: %s x%d = %.2f%n", order.getId(), order.getCustomer(),
                        order.getQuantity(), order.getTotal());
                sum += order.getTotal();
                count++;
            }
        }
        System.out.printf("  итого по товару %s: %d зак., %.2f%n", product, count, sum);
    }

    void printReport() {
        System.out.println("##### ОТЧЁТ #####");
        if (orders.isEmpty()) {
            System.out.println("Данных нет");
            return;
        }
        System.out.println("1. Общие показатели");
        System.out.println("   заказов: " + orders.size());
        System.out.println("   сумма: " + formatAmount(totalAmount()));
        System.out.println("   среднее: " + formatAmount(averageAmount()));
        System.out.println("   крупных (от 10 шт.): " + countLargeOrders(10));
        System.out.println("2. По статусам");
        for (Map.Entry<String, Long> entry : countByStatusLabel().entrySet()) {
            System.out.println("   " + padRight(entry.getKey(), 10) + entry.getValue());
        }
        System.out.println("3. Лучшие клиенты");
        List<CustomerTotal> top = topCustomers(3);
        for (CustomerTotal item : top) {
            System.out.printf("   %s: %.2f%n", item.customer(), item.total());
        }
        System.out.println("4. Подробно по клиентам");
        for (String customer : distinctCustomers()) {
            printByCustomer(customer);
        }
        System.out.println("5. Подробно по товарам");
        Map<String, Integer> products = new LinkedHashMap<>();
        for (Order order : orders) {
            products.merge(order.getProduct(), order.getQuantity(), Integer::sum);
        }
        for (Map.Entry<String, Integer> entry : products.entrySet()) {
            printByProduct(entry.getKey());
        }
        System.out.println("6. Подозрительные заказы");
        List<Integer> anomalies = findAnomalies();
        if (anomalies.isEmpty()) {
            System.out.println("   не найдено");
        } else {
            for (Integer id : anomalies) {
                System.out.println("   заказ " + id);
            }
        }
        List<String> expensive = expensiveProducts(1000);
        System.out.println("7. Дорогие товары (от 1000): " + expensive);
        System.out.println("##### КОНЕЦ ОТЧЁТА #####");
    }
}

interface Describable {
    String describe();

    default String shortInfo() {
        return describe().toUpperCase();
    }
}

enum OrderStatus {
    NEW("Новый"),
    PAID("Оплачен"),
    SHIPPED("Отправлен"),
    CANCELLED("Отменён");

    private final String label;

    OrderStatus(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }

    boolean canMoveTo(OrderStatus next) {
        return switch (this) {
            case NEW -> next == PAID || next == CANCELLED;
            case PAID -> next == SHIPPED || next == CANCELLED;
            case SHIPPED, CANCELLED -> false;
        };
    }
}

class Order implements Describable {
    private final int id;
    private final String customer;
    private final String product;
    private int quantity;
    private double unitPrice;
    private final double basePrice;
    private OrderStatus status = OrderStatus.NEW;

    Order(int id, String customer, String product, int quantity, double unitPrice) {
        this.id = id;
        this.customer = customer;
        this.product = product;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
        this.basePrice = unitPrice;
    }

    int getId() {
        return id;
    }

    String getCustomer() {
        return customer;
    }

    String getProduct() {
        return product;
    }

    int getQuantity() {
        return quantity;
    }

    double getUnitPrice() {
        return unitPrice;
    }

    double getBasePrice() {
        return basePrice;
    }

    OrderStatus getStatus() {
        return status;
    }

    void setStatus(OrderStatus status) {
        this.status = status;
    }

    void setUnitPrice(double unitPrice) {
        this.unitPrice = unitPrice;
    }

    void addQuantity(int extra) {
        this.quantity += extra;
    }

    double getTotal() {
        return quantity * unitPrice;
    }

    Order copy() {
        Order clone = new Order(id, customer, product, quantity, unitPrice);
        clone.status = status;
        return clone;
    }

    @Override
    public String describe() {
        return "Заказ #" + id + ": " + customer + " купил " + product + " (" + quantity + " шт. по "
                + Main.formatAmount(unitPrice) + ") — " + status.getLabel();
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof Order)) {
            return false;
        }
        return id == ((Order) other).id;
    }

    @Override
    public int hashCode() {
        return Integer.hashCode(id);
    }

    @Override
    public String toString() {
        return "Order[" + id + "]";
    }
}

record CustomerTotal(String customer, int orders, double total) {
    CustomerTotal {
        if (orders < 0) {
            throw new IllegalArgumentException("orders < 0");
        }
    }

    double average() {
        return orders == 0 ? 0 : total / orders;
    }
}

class OrderParseException extends Exception {
    private static final long serialVersionUID = 1L;

    OrderParseException(String message) {
        super(message);
    }
}

class OrderValidationException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    OrderValidationException(String message) {
        super(message);
    }
}
