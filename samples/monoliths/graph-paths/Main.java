import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Сеть дорог между городами: узлы, рёбра с весами, поиск путей, компоненты связности.
 *
 * Программа читает команды из стандартного ввода построчно и хранит граф в памяти. Весь код собран
 * в одном классе: разбор команд, проверка, обходы и кратчайшие пути, преобразования графа и вывод.
 * Используется как пример монолита с алгоритмами и массивами для диагностики и декомпозиции.
 */
public class Main {

    private static final int MAX_NODES = 200;
    private static final int MAX_WEIGHT = 100000;
    private static final int INFINITY = Integer.MAX_VALUE / 2;
    private static final String HUB_NAME = "Центр";
    private static final String ISOLATED_LABEL = "Изолированный";

    private final List<String> names = new ArrayList<>();
    private final List<Edge> edges = new ArrayList<>();
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
            } catch (GraphInputException e) {
                errorCount++;
                System.out.println("Ошибка ввода: " + e.getMessage());
            } catch (GraphException e) {
                errorCount++;
                System.out.println("Ошибка графа: " + e.getMessage());
            }
        }
    }

    private boolean processCommand(String line, Scanner in) throws GraphInputException {
        String[] parts = tokenize(line);
        String command = parts[0].toLowerCase();
        switch (command) {
            case "node":
                addNode(normalizeName(requireArg(parts, 1, "имя узла")));
                break;
            case "edge":
                addEdge(parseEdge(parts, 1, false));
                break;
            case "oneway":
                addEdge(parseEdge(parts, 1, true));
                break;
            case "batch": {
                int count = parseInt(requireArg(parts, 1, "количество рёбер"), "количество рёбер");
                List<Edge> batch = readBatch(in, count);
                System.out.printf("Принято рёбер: %d из %d%n", addAll(batch), count);
                break;
            }
            case "remove":
                removeNode(normalizeName(requireArg(parts, 1, "имя узла")));
                break;
            case "cut":
                removeEdge(normalizeName(requireArg(parts, 1, "первый узел")),
                        normalizeName(requireArg(parts, 2, "второй узел")));
                break;
            case "list":
                printNodes();
                break;
            case "edges":
                printEdges();
                break;
            case "neighbors":
                printNeighbors(normalizeName(requireArg(parts, 1, "имя узла")));
                break;
            case "path":
                printPath(normalizeName(requireArg(parts, 1, "откуда")), normalizeName(requireArg(parts, 2, "куда")));
                break;
            case "bfs":
                printBfs(normalizeName(requireArg(parts, 1, "старт")));
                break;
            case "dfs":
                printDfs(normalizeName(requireArg(parts, 1, "старт")));
                break;
            case "components":
                printComponents();
                break;
            case "matrix":
                printMatrix();
                break;
            case "floyd":
                printFloyd();
                break;
            case "cycle":
                System.out.println(hasCycle() ? "Цикл найден" : "Циклов нет");
                break;
            case "merge":
                System.out.println("Объединено параллельных рёбер: " + mergeParallelEdges());
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
        return line.trim().replaceAll("\\s+", " ").split(" ");
    }

    private String requireArg(String[] parts, int index, String what) throws GraphInputException {
        if (index >= parts.length) {
            throw new GraphInputException("не указан параметр: " + what);
        }
        return parts[index];
    }

    private int parseInt(String token, String what) throws GraphInputException {
        try {
            return Integer.parseInt(token);
        } catch (NumberFormatException e) {
            throw new GraphInputException("«" + token + "» не число (" + what + ")");
        }
    }

    private Edge parseEdge(String[] parts, int from, boolean directed) throws GraphInputException {
        String first = normalizeName(requireArg(parts, from, "первый узел"));
        String second = normalizeName(requireArg(parts, from + 1, "второй узел"));
        int weight = parseInt(requireArg(parts, from + 2, "вес"), "вес");
        return new Edge(first, second, weight, directed);
    }

    static String normalizeName(String raw) {
        String name = raw.replace('_', ' ').trim();
        if (name.isEmpty()) {
            return name;
        }
        return Character.toUpperCase(name.charAt(0)) + name.substring(1);
    }

    private List<Edge> readBatch(Scanner in, int count) {
        List<Edge> batch = new ArrayList<>();
        for (int i = 0; i < count && in.hasNextLine(); i++) {
            String[] parts = tokenize(in.nextLine());
            try {
                batch.add(parseEdge(parts, 0, false));
            } catch (GraphInputException e) {
            }
        }
        return batch;
    }

    // ------------------------------------------------------------------
    // Проверка данных
    // ------------------------------------------------------------------

    private void checkNodeName(String name) {
        if (name == null || name.isEmpty()) {
            throw new GraphException("пустое имя узла");
        }
        if (name.length() > 30) {
            throw new GraphException("имя узла «" + name + "» слишком длинное");
        }
        if (Character.isDigit(name.charAt(0))) {
            throw new GraphException("имя узла «" + name + "» начинается с цифры");
        }
    }

    private void checkWeight(Edge edge) {
        if (edge.getWeight() <= 0) {
            throw new GraphException("вес ребра " + edge.getFrom() + "-" + edge.getTo() + " должен быть положительным");
        }
        if (edge.getWeight() > MAX_WEIGHT) {
            throw new GraphException("вес ребра " + edge.getFrom() + "-" + edge.getTo() + " больше " + MAX_WEIGHT);
        }
    }

    private int idOf(String name) {
        int id = names.indexOf(name);
        if (id < 0) {
            throw new GraphException("узел «" + name + "» не найден");
        }
        return id;
    }

    // ------------------------------------------------------------------
    // Изменение графа
    // ------------------------------------------------------------------

    void addNode(String name) {
        checkNodeName(name);
        if (names.contains(name)) {
            throw new GraphException("узел «" + name + "» уже есть");
        }
        if (names.size() >= MAX_NODES) {
            throw new GraphException("в графе уже " + MAX_NODES + " узлов");
        }
        names.add(name);
        System.out.println("Добавлен узел " + name);
    }

    void addEdge(Edge edge) {
        checkWeight(edge);
        if (edge.getFrom().equals(edge.getTo())) {
            throw new GraphException("петля в узле «" + edge.getFrom() + "» не допускается");
        }
        for (String name : new String[] {edge.getFrom(), edge.getTo()}) {
            if (!names.contains(name)) {
                addNode(name);
            }
        }
        edges.add(edge);
        System.out.println("Добавлено ребро " + edge.describe());
    }

    int addAll(List<Edge> batch) {
        int accepted = 0;
        for (Edge edge : batch) {
            try {
                addEdge(edge);
                accepted++;
            } catch (GraphException e) {
                errorCount++;
                System.out.println("Пропущено ребро " + edge.getFrom() + "-" + edge.getTo() + ": " + e.getMessage());
            }
        }
        return accepted;
    }

    void removeNode(String name) {
        int id = idOf(name);
        int removedEdges = 0;
        for (int i = edges.size() - 1; i >= 0; i--) {
            Edge edge = edges.get(i);
            if (edge.getFrom().equals(name) || edge.getTo().equals(name)) {
                edges.remove(i);
                removedEdges++;
            }
        }
        names.remove(id);
        System.out.println("Удалён узел " + name + " и рёбер: " + removedEdges);
    }

    void removeEdge(String first, String second) {
        int removed = 0;
        Edge[] snapshot = edges.toArray(new Edge[0]);
        for (Edge edge : snapshot) {
            boolean forward = edge.getFrom().equals(first) && edge.getTo().equals(second);
            boolean backward = !edge.isDirected() && edge.getFrom().equals(second) && edge.getTo().equals(first);
            if (forward || backward) {
                edges.remove(edge);
                removed++;
            }
        }
        if (removed == 0) {
            throw new GraphException("ребра " + first + "-" + second + " нет");
        }
        System.out.println("Удалено рёбер: " + removed);
    }

    // ------------------------------------------------------------------
    // Представления графа
    // ------------------------------------------------------------------

    List<List<Integer>> adjacency() {
        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < names.size(); i++) {
            result.add(new ArrayList<>());
        }
        for (Edge edge : edges) {
            int from = names.indexOf(edge.getFrom());
            int to = names.indexOf(edge.getTo());
            result.get(from).add(to);
            if (!edge.isDirected()) {
                result.get(to).add(from);
            }
        }
        for (List<Integer> row : result) {
            Collections.sort(row);
        }
        return result;
    }

    int[][] buildMatrix() {
        int n = names.size();
        int[][] matrix = new int[n][n];
        for (int[] row : matrix) {
            Arrays.fill(row, INFINITY);
        }
        for (int i = 0; i < n; i++) {
            matrix[i][i] = 0;
        }
        for (Edge edge : edges) {
            int from = names.indexOf(edge.getFrom());
            int to = names.indexOf(edge.getTo());
            matrix[from][to] = Math.min(matrix[from][to], edge.getWeight());
            if (!edge.isDirected()) {
                matrix[to][from] = Math.min(matrix[to][from], edge.getWeight());
            }
        }
        return matrix;
    }

    int degree(String name) {
        int degree = 0;
        for (Edge edge : edges) {
            if (edge.getFrom().equals(name) || edge.getTo().equals(name)) {
                degree++;
            }
        }
        return degree;
    }

    // ------------------------------------------------------------------
    // Алгоритмы
    // ------------------------------------------------------------------

    List<Integer> bfsOrder(int start) {
        List<List<Integer>> graph = adjacency();
        boolean[] seen = new boolean[names.size()];
        List<Integer> order = new ArrayList<>();
        Queue<Integer> queue = new LinkedList<>();
        queue.add(start);
        seen[start] = true;
        while (!queue.isEmpty()) {
            int current = queue.remove();
            order.add(current);
            for (int next : graph.get(current)) {
                if (!seen[next]) {
                    seen[next] = true;
                    queue.add(next);
                }
            }
        }
        return order;
    }

    List<Integer> dfsOrder(int start) {
        List<Integer> order = new ArrayList<>();
        visit(start, adjacency(), new boolean[names.size()], order);
        return order;
    }

    private void visit(int node, List<List<Integer>> graph, boolean[] seen, List<Integer> order) {
        seen[node] = true;
        order.add(node);
        for (int next : graph.get(node)) {
            if (!seen[next]) {
                visit(next, graph, seen, order);
            }
        }
    }

    Route shortestPath(int from, int to) {
        int n = names.size();
        int[][] matrix = buildMatrix();
        int[] distance = new int[n];
        int[] previous = new int[n];
        boolean[] done = new boolean[n];
        Arrays.fill(distance, INFINITY);
        Arrays.fill(previous, -1);
        distance[from] = 0;
        for (int step = 0; step < n; step++) {
            int best = -1;
            for (int i = 0; i < n; i++) {
                if (!done[i] && distance[i] < INFINITY && (best < 0 || distance[i] < distance[best])) {
                    best = i;
                }
            }
            if (best < 0) {
                break;
            }
            done[best] = true;
            for (int j = 0; j < n; j++) {
                if (!done[j] && matrix[best][j] < INFINITY && distance[best] + matrix[best][j] < distance[j]) {
                    distance[j] = distance[best] + matrix[best][j];
                    previous[j] = best;
                }
            }
        }
        if (distance[to] >= INFINITY) {
            return new Route(List.of(), -1);
        }
        List<Integer> path = new ArrayList<>();
        for (int at = to; at >= 0; at = previous[at]) {
            path.add(0, at);
        }
        return new Route(path, distance[to]);
    }

    List<List<String>> components() {
        List<List<Integer>> graph = adjacency();
        List<Integer> visited = new ArrayList<>();
        List<List<String>> result = new ArrayList<>();
        for (int start = 0; start < names.size(); start++) {
            if (visited.contains(start)) {
                continue;
            }
            List<String> group = new ArrayList<>();
            for (int node : bfsFrom(graph, start)) {
                if (!visited.contains(node)) {
                    visited.add(node);
                    group.add(names.get(node));
                }
            }
            Collections.sort(group);
            result.add(group);
        }
        return result;
    }

    private List<Integer> bfsFrom(List<List<Integer>> graph, int start) {
        List<Integer> order = new ArrayList<>();
        Queue<Integer> queue = new LinkedList<>();
        boolean[] seen = new boolean[graph.size()];
        queue.add(start);
        seen[start] = true;
        while (!queue.isEmpty()) {
            int current = queue.remove();
            order.add(current);
            for (int next : graph.get(current)) {
                if (!seen[next]) {
                    seen[next] = true;
                    queue.add(next);
                }
            }
        }
        return order;
    }

    boolean hasCycle() {
        int n = names.size();
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) {
            parent[i] = i;
        }
        for (Edge edge : edges) {
            int a = find(parent, names.indexOf(edge.getFrom()));
            int b = find(parent, names.indexOf(edge.getTo()));
            if (a == b) {
                return true;
            }
            parent[a] = b;
        }
        return false;
    }

    private int find(int[] parent, int node) {
        while (parent[node] != node) {
            parent[node] = parent[parent[node]];
            node = parent[node];
        }
        return node;
    }

    int[][] floyd() {
        int[][] dist = buildMatrix();
        int n = names.size();
        for (int k = 0; k < n; k++) {
            for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    if (dist[i][k] < INFINITY && dist[k][j] < INFINITY && dist[i][k] + dist[k][j] < dist[i][j]) {
                        dist[i][j] = dist[i][k] + dist[k][j];
                    }
                }
            }
        }
        return dist;
    }

    int countIsolated() {
        int count = 0;
        for (String name : names) {
            if (degree(name) == 0) {
                count++;
            }
        }
        return count;
    }

    int countLeaves() {
        int count = 0;
        for (String name : names) {
            if (degree(name) == 1) {
                count++;
            }
        }
        return count;
    }

    int countHubs() {
        int count = 0;
        for (String name : names) {
            if (degree(name) >= 3) {
                count++;
            }
        }
        return count;
    }

    String busiest() {
        String best = "";
        int bestDegree = -1;
        for (String name : names) {
            if (degree(name) > bestDegree) {
                best = name;
                bestDegree = degree(name);
            }
        }
        return best;
    }

    Map<Integer, Long> degreeHistogram() {
        return names.stream()
                .collect(Collectors.groupingBy(name -> degree(name), TreeMap::new, Collectors.counting()));
    }

    NodeKind kindOf(String name) {
        int degree = degree(name);
        if (degree == 0) {
            return NodeKind.ISOLATED;
        }
        return degree >= 3 ? NodeKind.HUB : NodeKind.REGULAR;
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

    // ------------------------------------------------------------------
    // Преобразования графа
    // ------------------------------------------------------------------

    int mergeParallelEdges() {
        List<Edge> merged = new ArrayList<>();
        for (Edge candidate : edges) {
            boolean found = false;
            for (Edge existing : merged) {
                boolean same = existing.getFrom().equals(candidate.getFrom())
                        && existing.getTo().equals(candidate.getTo());
                boolean reverse = !existing.isDirected() && !candidate.isDirected()
                        && existing.getFrom().equals(candidate.getTo())
                        && existing.getTo().equals(candidate.getFrom());
                if ((same || reverse) && existing.isDirected() == candidate.isDirected()) {
                    existing.setWeight(Math.min(existing.getWeight(), candidate.getWeight()));
                    found = true;
                    break;
                }
            }
            if (!found) {
                merged.add(candidate.copy());
            }
        }
        int removed = edges.size() - merged.size();
        edges.clear();
        edges.addAll(merged);
        return removed;
    }

    String routeString(Route route) {
        String text = "";
        for (int i = 0; i < route.nodes().size(); i++) {
            if (i > 0) {
                text += " -> ";
            }
            text += names.get(route.nodes().get(i));
        }
        return text;
    }

    // ------------------------------------------------------------------
    // Вывод
    // ------------------------------------------------------------------

    void printHeader() {
        System.out.println("=== Сеть дорог ===");
        System.out.println("Команды: node, edge, oneway, batch, path, bfs, dfs, components, matrix, report, quit");
        System.out.println(repeat('-', 40));
    }

    void printFooter() {
        System.out.println(repeat('-', 40));
        System.out.printf("Команд: %d, ошибок: %d, узлов: %d, рёбер: %d%n", commandCount, errorCount, names.size(),
                edges.size());
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

    void printNodes() {
        if (names.isEmpty()) {
            System.out.println("Узлов нет");
            return;
        }
        for (int i = 0; i < names.size(); i++) {
            String name = names.get(i);
            String mark = name == HUB_NAME ? "*" : " ";
            System.out.println(padLeft(String.valueOf(i), 3) + " " + mark + padRight(name, 16) + "степень "
                    + degree(name) + ", " + kindOf(name).getLabel());
        }
    }

    void printEdges() {
        if (edges.isEmpty()) {
            System.out.println("Рёбер нет");
            return;
        }
        for (Edge edge : edges) {
            System.out.println(edge.describe());
        }
    }

    void printNeighbors(String name) {
        int id = idOf(name);
        List<Integer> around = adjacency().get(id);
        if (around.isEmpty()) {
            System.out.println(name + ": соседей нет");
            return;
        }
        List<String> list = new ArrayList<>();
        for (int node : around) {
            list.add(names.get(node));
        }
        System.out.println(name + ": " + String.join(", ", list));
    }

    void printPath(String from, String to) {
        Route route = shortestPath(idOf(from), idOf(to));
        if (route.nodes().isEmpty()) {
            System.out.println("Пути из «" + from + "» в «" + to + "» нет");
            return;
        }
        System.out.println(routeString(route));
        System.out.println("Расстояние: " + route.distance() + ", остановок: " + (route.nodes().size() - 1));
    }

    void printBfs(String start) {
        List<String> result = new ArrayList<>();
        for (int node : bfsOrder(idOf(start))) {
            result.add(names.get(node));
        }
        System.out.println("Обход в ширину: " + String.join(" ", result));
    }

    void printDfs(String start) {
        List<String> result = new ArrayList<>();
        for (int node : dfsOrder(idOf(start))) {
            result.add(names.get(node));
        }
        System.out.println("Обход в глубину: " + String.join(" ", result));
    }

    void printComponents() {
        List<List<String>> groups = components();
        if (groups.isEmpty()) {
            System.out.println("Узлов нет");
            return;
        }
        System.out.println("Компонент связности: " + groups.size());
        for (int i = 0; i < groups.size(); i++) {
            System.out.println("  " + (i + 1) + ": " + groups.get(i));
        }
    }

    void printMatrix() {
        int[][] matrix = buildMatrix();
        if (matrix.length == 0) {
            System.out.println("Узлов нет");
            return;
        }
        for (int[] row : matrix) {
            StringBuilder line = new StringBuilder();
            for (int value : row) {
                line.append(padLeft(value >= INFINITY ? "-" : String.valueOf(value), 6));
            }
            System.out.println(line);
        }
    }

    void printFloyd() {
        int[][] dist = floyd();
        int diameter = 0;
        int unreachable = 0;
        for (int i = 0; i < dist.length; i++) {
            for (int j = 0; j < dist.length; j++) {
                if (i == j) {
                    continue;
                }
                if (dist[i][j] >= INFINITY) {
                    unreachable++;
                } else {
                    diameter = Math.max(diameter, dist[i][j]);
                }
            }
        }
        System.out.println("Диаметр: " + diameter + ", недостижимых пар: " + unreachable);
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
        if (names.isEmpty()) {
            System.out.println("Данных нет");
            return;
        }
        System.out.println("1. Размер");
        System.out.println("   узлов: " + names.size());
        System.out.println("   рёбер: " + edges.size());
        int directed = 0;
        int total = 0;
        for (Edge edge : edges) {
            total += edge.getWeight();
            if (edge.isDirected()) {
                directed++;
            }
        }
        System.out.println("   односторонних: " + directed);
        System.out.println("   суммарный вес: " + total);
        System.out.println("2. Узлы по роли");
        System.out.println("   изолированных: " + countIsolated());
        System.out.println("   листьев: " + countLeaves());
        System.out.println("   узлов-центров: " + countHubs());
        System.out.println("   самый загруженный: " + busiest());
        System.out.println("3. Распределение степеней");
        for (Map.Entry<Integer, Long> entry : degreeHistogram().entrySet()) {
            System.out.println("   степень " + entry.getKey() + ": " + entry.getValue());
        }
        System.out.println("4. Связность");
        List<List<String>> groups = components();
        System.out.println("   компонент: " + groups.size());
        int biggest = 0;
        for (List<String> group : groups) {
            biggest = Math.max(biggest, group.size());
        }
        System.out.println("   самая большая: " + biggest);
        System.out.println("   циклы: " + (hasCycle() ? "есть" : "нет"));
        System.out.println("5. Тяжёлые рёбра");
        List<Edge> heavy = topN(edges, Comparator.comparingInt(Edge::getWeight).reversed()
                .thenComparing(Edge::getFrom).thenComparing(Edge::getTo), 3);
        for (Edge edge : heavy) {
            System.out.println("   " + edge.describe());
        }
        System.out.println("6. Названия");
        System.out.println("   последнее по алфавиту: " + maxOf(names, ""));
        String label = NodeKind.ISOLATED.getLabel() == ISOLATED_LABEL ? "метка совпала" : "метка другая";
        System.out.println("   " + label);
        System.out.println("##### КОНЕЦ ОТЧЁТА #####");
    }
}

enum NodeKind {
    ISOLATED("Изолированный"),
    REGULAR("Обычный"),
    HUB("Центр");

    private final String label;

    NodeKind(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }
}

class Edge {
    private final String from;
    private final String to;
    private int weight;
    private final boolean directed;

    Edge(String from, String to, int weight, boolean directed) {
        this.from = from;
        this.to = to;
        this.weight = weight;
        this.directed = directed;
    }

    String getFrom() {
        return from;
    }

    String getTo() {
        return to;
    }

    int getWeight() {
        return weight;
    }

    boolean isDirected() {
        return directed;
    }

    void setWeight(int weight) {
        this.weight = weight;
    }

    Edge copy() {
        return new Edge(from, to, weight, directed);
    }

    String describe() {
        return from + (directed ? " -> " : " -- ") + to + " (" + weight + ")";
    }
}

record Route(List<Integer> nodes, int distance) {
}

class GraphInputException extends Exception {
    private static final long serialVersionUID = 1L;

    GraphInputException(String message) {
        super(message);
    }
}

class GraphException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    GraphException(String message) {
        super(message);
    }
}
