import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

record Point(int x, int y) {
    static final Point ORIGIN = new Point(0, 0);

    Point {
        if (x < -1000 || y < -1000) {
            throw new IllegalArgumentException("координата слишком мала");
        }
    }

    static Point of(int value) {
        return new Point(value, value);
    }

    double distanceTo(Point other) {
        int dx = x - other.x;
        int dy = y - other.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    Point plus(Point other) {
        return new Point(x + other.x, y + other.y);
    }
}

record Segment(Point from, Point to) {
    double length() {
        return from.distanceTo(to);
    }

    record Label(String text, int priority) {
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();
        List<Point> points = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            try {
                points.add(new Point(in.nextInt(), in.nextInt()));
            } catch (IllegalArgumentException e) {
                System.out.println("ошибка: " + e.getMessage());
            }
        }
        Point sum = Point.ORIGIN;
        for (Point point : points) {
            System.out.println(point + " расстояние " + String.format("%.3f", point.distanceTo(Point.ORIGIN)));
            sum = sum.plus(point);
        }
        System.out.println("сумма " + sum + " x=" + sum.x() + " y=" + sum.y());
        System.out.println(Point.of(3).equals(new Point(3, 3)) + " " + Point.of(3).equals(Point.of(4)));
        if (points.size() >= 2) {
            Segment segment = new Segment(points.get(0), points.get(1));
            System.out.println(segment + " длина " + String.format("%.3f", segment.length()));
        }
        Segment.Label label = new Segment.Label("метка", 2);
        System.out.println(label + " " + label.text().length());
    }
}
