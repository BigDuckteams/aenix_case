import java.util.EnumMap;
import java.util.Map;
import java.util.Scanner;

enum Planet {
    MERCURY(3.303e+23, 2.4397e6),
    EARTH(5.976e+24, 6.37814e6),
    JUPITER(1.9e+27, 7.1492e7);

    private final double mass;
    private final double radius;

    Planet(double mass, double radius) {
        this.mass = mass;
        this.radius = radius;
    }

    double surfaceGravity() {
        return 6.67300E-11 * mass / (radius * radius);
    }
}

enum Operation {
    ADD("+") {
        @Override
        int apply(int a, int b) {
            return a + b;
        }
    },
    MULTIPLY("*") {
        @Override
        int apply(int a, int b) {
            return a * b;
        }
    },
    SUBTRACT("-") {
        @Override
        int apply(int a, int b) {
            return a - b;
        }
    };

    private final String symbol;

    Operation(String symbol) {
        this.symbol = symbol;
    }

    String symbol() {
        return symbol;
    }

    abstract int apply(int a, int b);
}

enum Level {
    LOW, MEDIUM, HIGH
}

public class Main {
    static String describe(Level level) {
        switch (level) {
            case LOW:
                return "низкий";
            case MEDIUM:
                return "средний";
            default:
                return "высокий";
        }
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int a = in.nextInt();
        int b = in.nextInt();
        String levelName = in.next();

        for (Operation operation : Operation.values()) {
            System.out.println(a + " " + operation.symbol() + " " + b + " = " + operation.apply(a, b)
                    + " (" + operation.name() + ", " + operation.ordinal() + ")");
        }
        for (Planet planet : Planet.values()) {
            System.out.printf("%s: %.2f%n", planet, planet.surfaceGravity());
        }
        try {
            Level level = Level.valueOf(levelName);
            System.out.println(level + " -> " + describe(level) + " " + level.compareTo(Level.MEDIUM));
        } catch (IllegalArgumentException e) {
            System.out.println("нет такого уровня: " + levelName);
        }
        Map<Level, Integer> counts = new EnumMap<>(Level.class);
        for (Level level : Level.values()) {
            counts.put(level, level.name().length());
        }
        System.out.println(counts);
        String text = switch (Level.HIGH) {
            case LOW -> "l";
            case MEDIUM -> "m";
            case HIGH -> "h";
        };
        System.out.println(text);
    }
}
