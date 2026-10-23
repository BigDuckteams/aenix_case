import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

interface Shape {
    double area();

    default String describe() {
        return name() + " площадью " + String.format("%.2f", area());
    }

    String name();

    static Shape unitSquare() {
        return new Square(1);
    }
}

class Circle implements Shape {
    private final double radius;

    Circle(double radius) {
        this.radius = radius;
    }

    public double area() {
        return Math.PI * radius * radius;
    }

    public String name() {
        return "Круг";
    }
}

class Square implements Shape {
    private final double side;

    Square(double side) {
        this.side = side;
    }

    public double area() {
        return side * side;
    }

    public String name() {
        return "Квадрат";
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        List<Shape> shapes = new ArrayList<>();
        shapes.add(Shape.unitSquare());
        while (in.hasNext()) {
            String kind = in.next();
            double size = in.nextDouble();
            if (kind.equals("circle")) {
                shapes.add(new Circle(size));
            } else {
                shapes.add(new Square(size));
            }
        }
        for (Shape shape : shapes) {
            System.out.println(shape.describe());
        }
    }
}
