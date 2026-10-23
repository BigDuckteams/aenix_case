import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        int a = in.nextInt();
        long big = in.nextLong();

        byte b = (byte) a;
        short s = (short) a;
        char c = (char) ('A' + Math.abs(a) % 26);
        float f = a / 3f;
        double d = a / 3.0;
        boolean even = a % 2 == 0;

        Integer boxed = a;
        int unboxed = boxed + 1;
        Integer x1 = 127;
        Integer x2 = 127;
        Integer y1 = 1000;
        Integer y2 = 1000;
        Long wrapped = big;
        Double dd = d;
        Character ch = c;
        Boolean flag = even;

        System.out.println("byte=" + b + " short=" + s + " char=" + c);
        System.out.println("float=" + f + " double=" + d);
        System.out.println("boxed=" + boxed + " unboxed=" + unboxed);
        System.out.println("127 == 127: " + (x1 == x2) + ", 1000 equals 1000: " + y1.equals(y2));
        System.out.println(wrapped + " " + dd + " " + ch + " " + flag);

        int overflow = Integer.MAX_VALUE;
        overflow++;
        long safe = (long) Integer.MAX_VALUE + 1;
        System.out.println("overflow=" + overflow + " safe=" + safe);
        System.out.println("long -> int: " + (int) big);
        System.out.println("MIN=" + Integer.MIN_VALUE + " MAX=" + Long.MAX_VALUE);
    }
}
