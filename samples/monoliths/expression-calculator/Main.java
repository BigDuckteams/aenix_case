import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.function.DoubleBinaryOperator;
import java.util.function.DoubleUnaryOperator;
import java.util.stream.Collectors;

/**
 * Калькулятор выражений с переменными и функциями.
 *
 * Читает команды из стандартного ввода построчно: let, eval, tokens, rpn, tree, check, table и др.
 * Внутри собраны в одном классе токенизатор, рекурсивный разбор, вычисление, упрощение дерева и вывод.
 * Пример монолита для диагностики, оптимизации и декомпозиции.
 */
public class Main {

    private static final int MAX_EXPRESSION_LENGTH = 200;
    private static final int MAX_TABLE_ROWS = 200;
    private static final int MAX_POWER = 64;
    private static final String PI_NAME = "pi";
    private static final String NUMBER_LABEL = "число";

    private final List<Variable> variables = new ArrayList<>();
    private final List<String> history = new ArrayList<>();
    private final Map<String, DoubleUnaryOperator> unaryFunctions = new TreeMap<>();
    private final Map<String, DoubleBinaryOperator> binaryFunctions = new TreeMap<>();
    private final Map<String, Double> constants = new TreeMap<>();
    private List<Token> tokens = new ArrayList<>();
    private int position;
    private int commandCount;
    private int errorCount;
    private int evaluations;

    Main() {
        registerFunctions();
    }

    public static void main(String[] args) {
        Main app = new Main();
        try (Scanner in = new Scanner(System.in, StandardCharsets.UTF_8)) {
            app.run(in);
        }
        app.printFooter();
    }

    private void registerFunctions() {
        constants.put(PI_NAME, Math.PI);
        constants.put("e", Math.E);
        unaryFunctions.put("sqrt", Math::sqrt);
        unaryFunctions.put("abs", Math::abs);
        unaryFunctions.put("floor", Math::floor);
        unaryFunctions.put("ceil", Math::ceil);
        unaryFunctions.put("round", v -> (double) Math.round(v));
        unaryFunctions.put("neg", v -> -v);
        unaryFunctions.put("sq", v -> v * v);
        binaryFunctions.put("min", Math::min);
        binaryFunctions.put("max", Math::max);
        binaryFunctions.put("pow", (a, b) -> integerPower(a, (int) b));
        binaryFunctions.put("hyp", (a, b) -> Math.sqrt(a * a + b * b));
        binaryFunctions.put("avg", (a, b) -> (a + b) / 2);
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
            } catch (ExpressionException e) {
                errorCount++;
                System.out.println("Ошибка выражения: " + e.getMessage());
            } catch (EvalException e) {
                errorCount++;
                System.out.println("Ошибка вычисления: " + e.getMessage());
            }
        }
    }

    private boolean processCommand(String line, Scanner in) throws ExpressionException {
        String command = firstWord(line).toLowerCase();
        String rest = restOf(line);
        switch (command) {
            case "let":
                defineVariable(rest);
                break;
            case "eval":
                history.add(rest);
                System.out.println(rest + " = " + formatNumber(evaluateText(rest)));
                break;
            case "tokens":
                printTokens(tokenize(rest));
                break;
            case "rpn":
                System.out.println(rpnString(parse(rest)));
                break;
            case "tree":
                printTree(parse(rest), 0);
                break;
            case "simplify": {
                Node original = parse(rest);
                Node simple = simplify(original);
                System.out.println(show(original) + " => " + show(simple));
                System.out.println("Узлов: " + countNodes(original) + " -> " + countNodes(simple));
                break;
            }
            case "check":
                printCheck(rest);
                break;
            case "vars":
                printVariables();
                break;
            case "unset":
                unsetVariable(rest);
                break;
            case "used":
                System.out.println("Переменные: " + usedVariables(parse(rest)));
                break;
            case "table":
                printTable(rest);
                break;
            case "batch": {
                int count = parseCount(rest);
                System.out.printf("Вычислено выражений: %d из %d%n", evaluateBatch(in, count), count);
                break;
            }
            case "stats":
                printStats();
                break;
            case "history":
                printHistory();
                break;
            case "help":
                printHelp();
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

    private int parseCount(String text) throws ExpressionException {
        try {
            return Integer.parseInt(text.trim());
        } catch (NumberFormatException e) {
            throw new ExpressionException("«" + text + "» не число");
        }
    }

    private int evaluateBatch(Scanner in, int count) {
        int done = 0;
        for (int i = 0; i < count && in.hasNextLine(); i++) {
            String text = in.nextLine().trim();
            try {
                history.add(text);
                System.out.println(text + " = " + formatNumber(evaluateText(text)));
                done++;
            } catch (ExpressionException e) {
            }
        }
        return done;
    }

    private void defineVariable(String rest) throws ExpressionException {
        int equals = rest.indexOf('=');
        if (equals <= 0) {
            throw new ExpressionException("ожидалось: let имя = выражение");
        }
        String name = rest.substring(0, equals).trim();
        checkName(name);
        double value = evaluateText(rest.substring(equals + 1));
        Variable existing = findVariable(name);
        if (existing == null) {
            variables.add(new Variable(name, value));
        } else {
            existing.setValue(value);
        }
        history.add("let " + rest);
        System.out.println(name + " := " + formatNumber(value));
    }

    private void checkName(String name) throws ExpressionException {
        if (name.isEmpty() || !Character.isLetter(name.charAt(0))) {
            throw new ExpressionException("имя «" + name + "» должно начинаться с буквы");
        }
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            if (!Character.isLetterOrDigit(c) && c != '_') {
                throw new ExpressionException("в имени «" + name + "» недопустим символ «" + c + "»");
            }
        }
        if (constants.containsKey(name) || unaryFunctions.containsKey(name) || binaryFunctions.containsKey(name)) {
            throw new ExpressionException("имя «" + name + "» зарезервировано");
        }
    }

    private void unsetVariable(String name) throws ExpressionException {
        for (int i = 0; i < variables.size(); i++) {
            if (variables.get(i).getName().equals(name)) {
                variables.remove(i);
                System.out.println("Удалена переменная " + name);
                return;
            }
        }
        throw new ExpressionException("переменная «" + name + "» не найдена");
    }

    private Variable findVariable(String name) {
        for (Variable variable : variables) {
            if (variable.getName().equals(name)) {
                return variable;
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // Токенизатор
    // ------------------------------------------------------------------

    List<Token> tokenize(String text) throws ExpressionException {
        if (text.length() > MAX_EXPRESSION_LENGTH) {
            throw new ExpressionException("выражение длиннее " + MAX_EXPRESSION_LENGTH + " символов");
        }
        List<Token> result = new ArrayList<>();
        int i = 0;
        while (i < text.length()) {
            char c = text.charAt(i);
            if (Character.isWhitespace(c)) {
                i++;
            } else if (Character.isDigit(c) || c == '.') {
                int start = i;
                while (i < text.length() && (Character.isDigit(text.charAt(i)) || text.charAt(i) == '.')) {
                    i++;
                }
                result.add(new Token(TokenType.NUMBER, text.substring(start, i), start));
            } else if (Character.isLetter(c) || c == '_') {
                int start = i;
                while (i < text.length() && (Character.isLetterOrDigit(text.charAt(i)) || text.charAt(i) == '_')) {
                    i++;
                }
                result.add(new Token(TokenType.NAME, text.substring(start, i), start));
            } else if ("+-*/%^<>".indexOf(c) >= 0) {
                result.add(new Token(TokenType.OPERATOR, String.valueOf(c), i));
                i++;
            } else if (c == '(' || c == ')') {
                result.add(new Token(TokenType.PAREN, String.valueOf(c), i));
                i++;
            } else if (c == ',') {
                result.add(new Token(TokenType.COMMA, ",", i));
                i++;
            } else {
                throw new ExpressionException("неожиданный символ «" + c + "» в позиции " + (i + 1));
            }
        }
        result.add(new Token(TokenType.END, "", text.length()));
        return result;
    }

    // ------------------------------------------------------------------
    // Рекурсивный разбор
    // ------------------------------------------------------------------

    Node parse(String text) throws ExpressionException {
        tokens = tokenize(text);
        position = 0;
        Node root = parseComparison();
        if (peek().type() != TokenType.END) {
            throw new ExpressionException("лишний токен «" + peek().text() + "» в позиции " + (peek().position() + 1));
        }
        return root;
    }

    private Token peek() {
        return tokens.get(position);
    }

    private Token next() {
        Token token = tokens.get(position);
        if (token.type() != TokenType.END) {
            position++;
        }
        return token;
    }

    private boolean matches(TokenType type, String text) {
        return peek().type() == type && peek().text().equals(text);
    }

    private Node parseComparison() throws ExpressionException {
        Node left = parseAdditive();
        while (peek().type() == TokenType.OPERATOR && (peek().text().equals("<") || peek().text().equals(">"))) {
            String operator = next().text();
            Node right = parseAdditive();
            left = Node.binary(operator, left, right);
        }
        return left;
    }

    private Node parseAdditive() throws ExpressionException {
        Node left = parseMultiplicative();
        while (peek().type() == TokenType.OPERATOR && (peek().text().equals("+") || peek().text().equals("-"))) {
            String operator = next().text();
            Node right = parseMultiplicative();
            left = Node.binary(operator, left, right);
        }
        return left;
    }

    private Node parseMultiplicative() throws ExpressionException {
        Node left = parseUnary();
        while (peek().type() == TokenType.OPERATOR
                && (peek().text().equals("*") || peek().text().equals("/") || peek().text().equals("%"))) {
            String operator = next().text();
            Node right = parseUnary();
            left = Node.binary(operator, left, right);
        }
        return left;
    }

    private Node parseUnary() throws ExpressionException {
        if (matches(TokenType.OPERATOR, "-")) {
            next();
            return Node.unary("-", parseUnary());
        }
        if (matches(TokenType.OPERATOR, "+")) {
            next();
            return parseUnary();
        }
        return parsePower();
    }

    private Node parsePower() throws ExpressionException {
        Node base = parsePrimary();
        if (matches(TokenType.OPERATOR, "^")) {
            next();
            return Node.binary("^", base, parseUnary());
        }
        return base;
    }

    private Node parsePrimary() throws ExpressionException {
        Token token = next();
        switch (token.type()) {
            case NUMBER:
                try {
                    return Node.number(Double.parseDouble(token.text()));
                } catch (NumberFormatException e) {
                    throw new ExpressionException("неверное число «" + token.text() + "»");
                }
            case NAME:
                if (matches(TokenType.PAREN, "(")) {
                    next();
                    List<Node> arguments = new ArrayList<>();
                    if (!matches(TokenType.PAREN, ")")) {
                        arguments.add(parseComparison());
                        while (peek().type() == TokenType.COMMA) {
                            next();
                            arguments.add(parseComparison());
                        }
                    }
                    expect(")");
                    checkArity(token.text(), arguments.size());
                    return Node.call(token.text(), arguments);
                }
                return Node.variable(token.text());
            case PAREN:
                if (token.text().equals("(")) {
                    Node inner = parseComparison();
                    expect(")");
                    return inner;
                }
                throw new ExpressionException("неожиданная скобка в позиции " + (token.position() + 1));
            default:
                throw new ExpressionException("ожидалось число, имя или скобка, получено «"
                        + (token.text().isEmpty() ? "конец выражения" : token.text()) + "»");
        }
    }

    private void expect(String paren) throws ExpressionException {
        if (!matches(TokenType.PAREN, paren)) {
            throw new ExpressionException("ожидалась «" + paren + "» в позиции " + (peek().position() + 1));
        }
        next();
    }

    private void checkArity(String name, int count) throws ExpressionException {
        if (unaryFunctions.containsKey(name) && count != 1) {
            throw new ExpressionException("функция " + name + " принимает 1 аргумент, получено " + count);
        }
        if (binaryFunctions.containsKey(name) && count != 2) {
            throw new ExpressionException("функция " + name + " принимает 2 аргумента, получено " + count);
        }
        if (!unaryFunctions.containsKey(name) && !binaryFunctions.containsKey(name)) {
            throw new ExpressionException("неизвестная функция «" + name + "»");
        }
    }

    // ------------------------------------------------------------------
    // Вычисление
    // ------------------------------------------------------------------

    double evaluateText(String text) throws ExpressionException {
        return evaluate(parse(text));
    }

    double evaluate(Node node) {
        evaluations++;
        switch (node.getKind()) {
            case NUMBER:
                return node.getValue();
            case VARIABLE: {
                Variable variable = findVariable(node.getText());
                if (variable != null) {
                    return variable.getValue();
                }
                Double constant = constants.get(node.getText());
                if (constant == null) {
                    throw new EvalException("переменная «" + node.getText() + "» не задана");
                }
                return constant;
            }
            case UNARY:
                return -evaluate(node.child(0));
            case BINARY:
                return applyOperator(node.getText(), evaluate(node.child(0)), evaluate(node.child(1)));
            default: {
                String name = node.getText();
                if (unaryFunctions.containsKey(name)) {
                    return unaryFunctions.get(name).applyAsDouble(evaluate(node.child(0)));
                }
                return binaryFunctions.get(name).applyAsDouble(evaluate(node.child(0)), evaluate(node.child(1)));
            }
        }
    }

    double applyOperator(String operator, double left, double right) {
        switch (operator) {
            case "+":
                return left + right;
            case "-":
                return left - right;
            case "*":
                return left * right;
            case "/":
                if (right == 0) {
                    throw new EvalException("деление на ноль");
                }
                return left / right;
            case "%":
                if (right == 0) {
                    throw new EvalException("остаток от деления на ноль");
                }
                return left % right;
            case "^":
                return integerPower(left, (int) right);
            case "<":
                return left < right ? 1 : 0;
            default:
                return left > right ? 1 : 0;
        }
    }

    static double integerPower(double base, int exponent) {
        if (exponent < 0 || exponent > MAX_POWER) {
            throw new EvalException("показатель степени должен быть от 0 до " + MAX_POWER);
        }
        double result = 1;
        for (int i = 0; i < exponent; i++) {
            result *= base;
        }
        return result;
    }

    // ------------------------------------------------------------------
    // Анализ дерева
    // ------------------------------------------------------------------

    int countNodes(Node node) {
        int total = 1;
        for (Node child : node.getChildren()) {
            total += countNodes(child);
        }
        return total;
    }

    int depthOf(Node node) {
        int deepest = 0;
        for (Node child : node.getChildren()) {
            deepest = Math.max(deepest, depthOf(child));
        }
        return deepest + 1;
    }

    List<String> usedVariables(Node node) {
        List<String> names = new ArrayList<>();
        collectNames(node, names);
        Collections.sort(names);
        return names;
    }

    private void collectNames(Node node, List<String> names) {
        if (node.getKind() == NodeKind.VARIABLE && !constants.containsKey(node.getText())
                && !names.contains(node.getText())) {
            names.add(node.getText());
        }
        for (Node child : node.getChildren()) {
            collectNames(child, names);
        }
    }

    Map<String, Long> countOperators(Node node) {
        List<String> operators = new ArrayList<>();
        collectOperators(node, operators);
        return operators.stream().collect(Collectors.groupingBy(o -> o, TreeMap::new, Collectors.counting()));
    }

    private void collectOperators(Node node, List<String> operators) {
        if (node.getKind() == NodeKind.BINARY || node.getKind() == NodeKind.UNARY) {
            operators.add(node.getText());
        }
        for (Node child : node.getChildren()) {
            collectOperators(child, operators);
        }
    }

    boolean isConstantName(String name) {
        return name.toLowerCase() == PI_NAME || constants.containsKey(name);
    }

    String describeName(String name) {
        if (isConstantName(name)) {
            return "константа";
        }
        if (unaryFunctions.containsKey(name) || binaryFunctions.containsKey(name)) {
            return "функция";
        }
        return findVariable(name) != null ? "переменная" : "неизвестное имя";
    }

    List<ExprCount> countRepeats() {
        List<ExprCount> result = new ArrayList<>();
        for (String expression : history) {
            boolean found = false;
            for (ExprCount entry : result) {
                if (entry.getText().equals(expression)) {
                    entry.increment();
                    found = true;
                    break;
                }
            }
            if (!found) {
                result.add(new ExprCount(expression));
            }
        }
        return result;
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
    // Преобразования дерева
    // ------------------------------------------------------------------

    Node simplify(Node node) {
        List<Node> children = new ArrayList<>();
        for (Node child : node.getChildren()) {
            children.add(simplify(child));
        }
        switch (node.getKind()) {
            case UNARY:
                if (children.get(0).getKind() == NodeKind.NUMBER) {
                    return Node.number(-children.get(0).getValue());
                }
                return Node.unary(node.getText(), children.get(0));
            case BINARY: {
                Node left = children.get(0);
                Node right = children.get(1);
                if (left.getKind() == NodeKind.NUMBER && right.getKind() == NodeKind.NUMBER) {
                    try {
                        return Node.number(applyOperator(node.getText(), left.getValue(), right.getValue()));
                    } catch (EvalException e) {
                        return Node.binary(node.getText(), left, right);
                    }
                }
                if (node.getText().equals("+") && isNumber(right, 0)) {
                    return left;
                }
                if (node.getText().equals("+") && isNumber(left, 0)) {
                    return right;
                }
                if (node.getText().equals("*") && isNumber(right, 1)) {
                    return left;
                }
                if (node.getText().equals("*") && isNumber(left, 1)) {
                    return right;
                }
                return Node.binary(node.getText(), left, right);
            }
            case CALL:
                return Node.call(node.getText(), children);
            default:
                return node;
        }
    }

    private static boolean isNumber(Node node, double value) {
        return node.getKind() == NodeKind.NUMBER && node.getValue() == value;
    }

    List<String> toRpn(Node node) {
        List<String> output = new ArrayList<>();
        appendRpn(node, output);
        return output;
    }

    private void appendRpn(Node node, List<String> output) {
        for (Node child : node.getChildren()) {
            appendRpn(child, output);
        }
        switch (node.getKind()) {
            case NUMBER:
                output.add(formatNumber(node.getValue()));
                break;
            case UNARY:
                output.add("neg");
                break;
            case CALL:
                output.add(node.getText() + "/" + node.getChildren().size());
                break;
            default:
                output.add(node.getText());
        }
    }

    String rpnString(Node node) {
        String result = "";
        for (String item : toRpn(node)) {
            result += item + " ";
        }
        return result.trim();
    }

    double evaluateRpn(List<String> items) {
        List<Double> stack = new ArrayList<>();
        for (String item : items) {
            if (item.equals("neg")) {
                stack.add(-stack.remove(stack.size() - 1));
            } else if (item.contains("/") && item.length() > 2 && Character.isLetter(item.charAt(0))) {
                String name = item.substring(0, item.indexOf('/'));
                if (unaryFunctions.containsKey(name)) {
                    stack.add(unaryFunctions.get(name).applyAsDouble(stack.remove(stack.size() - 1)));
                } else {
                    double second = stack.remove(stack.size() - 1);
                    double first = stack.remove(stack.size() - 1);
                    stack.add(binaryFunctions.get(name).applyAsDouble(first, second));
                }
            } else if ("+-*/%^<>".contains(item) && item.length() == 1) {
                double right = stack.remove(stack.size() - 1);
                double left = stack.remove(stack.size() - 1);
                stack.add(applyOperator(item, left, right));
            } else if (Character.isLetter(item.charAt(0))) {
                Variable variable = findVariable(item);
                Double value = variable != null ? Double.valueOf(variable.getValue()) : constants.get(item);
                if (value == null) {
                    throw new EvalException("переменная «" + item + "» не задана");
                }
                stack.add(value);
            } else {
                stack.add(Double.parseDouble(item));
            }
        }
        return stack.get(stack.size() - 1);
    }

    // ------------------------------------------------------------------
    // Вывод
    // ------------------------------------------------------------------

    void printHeader() {
        System.out.println("=== Калькулятор выражений ===");
        System.out.println("Команды: let, eval, tokens, rpn, tree, simplify, check, vars, table, batch, report, quit");
        System.out.println(repeat('-', 40));
    }

    void printFooter() {
        System.out.println(repeat('-', 40));
        System.out.printf("Команд: %d, ошибок: %d, переменных: %d%n", commandCount, errorCount, variables.size());
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

    static String formatNumber(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            return String.valueOf(value);
        }
        if (value == Math.rint(value)) {
            return Math.abs(value) < 9.0e18 ? String.valueOf((long) value) : String.valueOf(value);
        }
        String text = String.format("%.6f", value);
        while (text.endsWith("0")) {
            text = text.substring(0, text.length() - 1);
        }
        return text;
    }

    String show(Node node) {
        switch (node.getKind()) {
            case NUMBER:
                return formatNumber(node.getValue());
            case VARIABLE:
                return node.getText();
            case UNARY:
                return "(-" + show(node.child(0)) + ")";
            case BINARY:
                return "(" + show(node.child(0)) + " " + node.getText() + " " + show(node.child(1)) + ")";
            default: {
                String args = node.getChildren().stream().map(this::show).collect(Collectors.joining(", "));
                return node.getText() + "(" + args + ")";
            }
        }
    }

    void printTokens(List<Token> list) {
        for (Token token : list) {
            if (token.type() != TokenType.END) {
                System.out.println(padRight(token.type().getLabel(), 12) + padRight(token.text(), 8)
                        + "позиция " + (token.position() + 1));
            }
        }
        System.out.println("Токенов: " + (list.size() - 1));
    }

    void printTree(Node node, int indent) {
        String label = node.getKind() == NodeKind.NUMBER ? formatNumber(node.getValue()) : node.getText();
        System.out.println(repeat(' ', indent * 2) + node.getKind().getLabel() + " " + label);
        for (Node child : node.getChildren()) {
            printTree(child, indent + 1);
        }
    }

    void printCheck(String text) throws ExpressionException {
        Node node = parse(text);
        double direct = evaluate(node);
        double viaRpn = evaluateRpn(toRpn(node));
        System.out.println("Дерево: " + formatNumber(direct) + ", ОПЗ: " + formatNumber(viaRpn));
        System.out.println(direct == viaRpn ? "Результаты совпали" : "Результаты расходятся");
    }

    void printVariables() {
        if (variables.isEmpty()) {
            System.out.println("Переменных нет");
            return;
        }
        List<Variable> sorted = new ArrayList<>(variables);
        sorted.sort((a, b) -> a.getName().compareTo(b.getName()));
        for (Variable variable : sorted) {
            System.out.println(padRight(variable.getName(), 12) + formatNumber(variable.getValue()));
        }
    }

    void printTable(String rest) throws ExpressionException {
        String[] parts = rest.split(" ");
        if (parts.length < 4) {
            throw new ExpressionException("table выражение от до шаг (x — переменная таблицы)");
        }
        int tail = parts.length - 3;
        String expression = String.join(" ", java.util.Arrays.copyOfRange(parts, 0, tail));
        double from = parseNumber(parts[tail]);
        double to = parseNumber(parts[tail + 1]);
        double step = parseNumber(parts[tail + 2]);
        if (step <= 0) {
            throw new ExpressionException("шаг должен быть положительным");
        }
        Node node = parse(expression);
        Variable x = findVariable("x");
        boolean created = x == null;
        double saved = created ? 0 : x.getValue();
        if (created) {
            x = new Variable("x", from);
            variables.add(x);
        }
        int rows = 0;
        for (double value = from; value <= to + 1e-9 && rows < MAX_TABLE_ROWS; value += step) {
            x.setValue(value);
            System.out.println("x = " + padRight(formatNumber(value), 8) + "f = " + formatNumber(evaluate(node)));
            rows++;
        }
        if (created) {
            variables.remove(x);
        } else {
            x.setValue(saved);
        }
        System.out.println("Строк: " + rows);
    }

    private double parseNumber(String text) throws ExpressionException {
        try {
            return Double.parseDouble(text.replace(',', '.'));
        } catch (NumberFormatException e) {
            throw new ExpressionException("«" + text + "» не число");
        }
    }

    void printStats() {
        List<ExprCount> repeats = countRepeats();
        if (repeats.isEmpty()) {
            System.out.println("Вычислений ещё не было");
            return;
        }
        int maxCount = 1;
        for (ExprCount entry : repeats) {
            maxCount = Math.max(maxCount, entry.getCount());
        }
        System.out.println("Выражений: " + history.size() + ", различных: " + repeats.size()
                + ", вычислений узлов: " + evaluations);
        for (ExprCount entry : repeats) {
            if (entry.getCount() == maxCount) {
                System.out.println("  чаще всего (" + maxCount + "): " + entry.getText());
                break;
            }
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

    void printHelp() {
        System.out.println("let имя = выражение   — задать переменную");
        System.out.println("eval выражение        — вычислить");
        System.out.println("tokens выражение      — разбить на токены");
        System.out.println("rpn выражение         — обратная польская запись");
        System.out.println("tree выражение        — дерево разбора");
        System.out.println("simplify выражение    — упростить константы");
        System.out.println("check выражение       — сверить дерево и ОПЗ");
        System.out.println("used выражение        — используемые переменные");
        System.out.println("table f от до шаг     — таблица значений по x");
        System.out.println("batch n               — следующие n строк вычислить пакетом");
        System.out.println("Функции: " + unaryFunctions.keySet() + " " + binaryFunctions.keySet());
        System.out.println("Константы: " + constants.keySet());
    }

    void printReport() {
        System.out.println("##### ОТЧЁТ #####");
        if (history.isEmpty() && variables.isEmpty()) {
            System.out.println("Данных нет");
            return;
        }
        System.out.println("1. Переменные");
        List<String> names = new ArrayList<>();
        for (Variable variable : variables) {
            names.add(variable.getName());
        }
        Collections.sort(names);
        System.out.println("   всего: " + names.size());
        for (String name : names) {
            System.out.println("   " + padRight(name, 10) + formatNumber(findVariable(name).getValue())
                    + "  (" + describeName(name) + ")");
        }
        System.out.println("2. Выражения");
        List<ExprCount> repeats = countRepeats();
        System.out.println("   в истории: " + history.size() + ", различных: " + repeats.size());
        int longest = 0;
        String longestText = "";
        for (String text : history) {
            if (text.length() > longest) {
                longest = text.length();
                longestText = text;
            }
        }
        System.out.println("   самое длинное: " + longestText);
        System.out.println("3. Операторы в истории");
        Map<String, Long> totals = new TreeMap<>();
        for (String text : history) {
            try {
                for (Map.Entry<String, Long> entry : countOperators(parse(text)).entrySet()) {
                    totals.merge(entry.getKey(), entry.getValue(), Long::sum);
                }
            } catch (ExpressionException e) {
                System.out.println("   не разобрано: " + text);
            }
        }
        for (Map.Entry<String, Long> entry : totals.entrySet()) {
            System.out.println("   " + padRight(entry.getKey(), 4) + entry.getValue());
        }
        System.out.println("4. Метка типа");
        String label = NUMBER_LABEL;
        System.out.println("   " + (NodeKind.NUMBER.getLabel() == label ? "метка числа совпала" : "метка числа другая"));
        System.out.println("5. Вычисления");
        System.out.println("   обращений к узлам: " + evaluations);
        System.out.println("   максимум по алфавиту среди имён: " + maxOf(names, ""));
        System.out.println("##### КОНЕЦ ОТЧЁТА #####");
    }
}

enum TokenType {
    NUMBER("число"),
    NAME("имя"),
    OPERATOR("оператор"),
    PAREN("скобка"),
    COMMA("запятая"),
    END("конец");

    private final String label;

    TokenType(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }
}

enum NodeKind {
    NUMBER("число"),
    VARIABLE("переменная"),
    UNARY("унарный"),
    BINARY("бинарный"),
    CALL("вызов");

    private final String label;

    NodeKind(String label) {
        this.label = label;
    }

    String getLabel() {
        return label;
    }
}

record Token(TokenType type, String text, int position) {
}

class Node {
    private final NodeKind kind;
    private final String text;
    private final double value;
    private final List<Node> children;

    private Node(NodeKind kind, String text, double value, List<Node> children) {
        this.kind = kind;
        this.text = text;
        this.value = value;
        this.children = children;
    }

    static Node number(double value) {
        return new Node(NodeKind.NUMBER, "", value, List.of());
    }

    static Node variable(String name) {
        return new Node(NodeKind.VARIABLE, name, 0, List.of());
    }

    static Node unary(String operator, Node operand) {
        return new Node(NodeKind.UNARY, operator, 0, List.of(operand));
    }

    static Node binary(String operator, Node left, Node right) {
        return new Node(NodeKind.BINARY, operator, 0, List.of(left, right));
    }

    static Node call(String name, List<Node> arguments) {
        return new Node(NodeKind.CALL, name, 0, List.copyOf(arguments));
    }

    NodeKind getKind() {
        return kind;
    }

    String getText() {
        return text;
    }

    double getValue() {
        return value;
    }

    List<Node> getChildren() {
        return children;
    }

    Node child(int index) {
        return children.get(index);
    }
}

class Variable {
    private final String name;
    private double value;

    Variable(String name, double value) {
        this.name = name;
        this.value = value;
    }

    String getName() {
        return name;
    }

    double getValue() {
        return value;
    }

    void setValue(double value) {
        this.value = value;
    }
}

class ExprCount {
    private final String text;
    private int count = 1;

    ExprCount(String text) {
        this.text = text;
    }

    String getText() {
        return text;
    }

    int getCount() {
        return count;
    }

    void increment() {
        count++;
    }
}

class ExpressionException extends Exception {
    private static final long serialVersionUID = 1L;

    ExpressionException(String message) {
        super(message);
    }
}

class EvalException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    EvalException(String message) {
        super(message);
    }
}
