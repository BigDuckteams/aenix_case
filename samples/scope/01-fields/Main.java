import java.util.Scanner;

class Settings {
    static final int MAX_ITEMS = 3;
    static final String PREFIX = "item-";
    static int created;

    final int id;
    String label;
    int count;
    double ratio;
    boolean active;
    int[] slots;

    Settings(String label) {
        this.id = ++created;
        this.label = label;
    }

    String show() {
        return PREFIX + id + " [" + label + "] count=" + count + " ratio=" + ratio
                + " active=" + active + " slots=" + (slots == null ? "нет" : String.valueOf(slots.length));
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = Math.min(in.nextInt(), Settings.MAX_ITEMS);
        for (int i = 0; i < n; i++) {
            Settings settings = new Settings(in.next());
            if (i % 2 == 0) {
                settings.count = i + 10;
                settings.active = true;
                settings.slots = new int[i + 1];
            }
            System.out.println(settings.show());
        }
        System.out.println("создано: " + Settings.created + " из " + Settings.MAX_ITEMS);
    }
}
