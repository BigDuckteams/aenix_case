import java.util.Scanner;

public class Main {
    static class Point {
        final int x;
        final int y;

        Point(int x, int y) {
            this.x = x;
            this.y = y;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) {
                return true;
            }
            if (!(o instanceof Point)) {
                return false;
            }
            Point p = (Point) o;
            return x == p.x && y == p.y;
        }

        @Override
        public int hashCode() {
            return 31 * x + y;
        }

        @Override
        public String toString() {
            return "(" + x + ", " + y + ")";
        }
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        String line = in.nextLine();
        int n = Integer.parseInt(in.nextLine().trim());

        System.out.println(line.length() + " " + line.toUpperCase() + " " + line.toLowerCase());
        System.out.println(line.substring(1, 4) + "|" + line.indexOf('о') + "|" + line.replace('о', '0'));
        System.out.println(line.contains("мир") + " " + line.startsWith("при") + " " + line.isEmpty());
        System.out.println(String.join("-", line.split(" ")) + " " + line.trim().charAt(0));
        System.out.println("a".compareTo("b") + " " + "abc".equals("abc") + " " + "ABC".equalsIgnoreCase("abc"));

        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) {
            sb.append(i).append(',');
        }
        sb.setLength(Math.max(0, sb.length() - 1));
        System.out.println(sb.reverse());

        System.out.println(Math.max(n, 3) + " " + Math.abs(-n) + " " + Math.pow(2, n) + " " + Math.sqrt(n)
                + " " + Math.floorMod(-n, 3) + " " + Math.round(2.5) + " " + Math.ceil(1.1));
        System.out.println(Integer.toBinaryString(n) + " " + Integer.toHexString(255) + " " + Long.parseLong("123456789012")
                + " " + Double.parseDouble("2.5") + " " + Integer.valueOf(n).equals(n));
        System.out.println(Character.isDigit('7') + " " + Character.isLetter('ж') + " " + Character.toUpperCase('ж')
                + " " + Boolean.parseBoolean("TRUE") + " " + Integer.compare(n, 3));

        Point p = new Point(1, 2);
        Point q = new Point(1, 2);
        System.out.println(p + " " + p.equals(q) + " " + (p == q) + " " + (p.hashCode() == q.hashCode()));
        System.out.println(java.util.Objects.equals(p, q) + " " + String.valueOf((Object) null));
        System.err.println("служебное сообщение");
    }
}
