import java.util.Scanner;

class Vehicle {
    static int created;
    protected final String kind;
    protected int wheels;

    static {
        created = 0;
    }

    {
        created++;
    }

    Vehicle(String kind) {
        this(kind, 4);
    }

    Vehicle(String kind, int wheels) {
        this.kind = kind;
        this.wheels = wheels;
        System.out.println("создан " + kind + " (" + wheels + " колёс)");
    }
}

class Bike extends Vehicle {
    private final boolean electric;

    Bike(boolean electric) {
        super("велосипед", 2);
        this.electric = electric;
    }

    Bike() {
        this(false);
    }

    String info() {
        return kind + (electric ? " электрический" : " обычный");
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int count = in.nextInt();
        for (int i = 0; i < count; i++) {
            String kind = in.next();
            if (kind.equals("bike")) {
                System.out.println(new Bike(in.nextBoolean()).info());
            } else if (kind.equals("plain")) {
                System.out.println(new Bike().info());
            } else {
                new Vehicle(kind);
            }
        }
        System.out.println("всего создано: " + Vehicle.created);
    }
}
