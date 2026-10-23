import java.lang.reflect.Method;
import java.net.URI;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Scanner;

/** Вне рамок кейса: рефлексия и сетевые типы (без реального обращения к сети). */
public class Main {
    public static String hello(String name) {
        return "привет, " + name;
    }

    public static void main(String[] args) throws Exception {
        Scanner in = new Scanner(System.in, "UTF-8");
        String name = in.next();
        String address = in.next();

        Class<?> type = Class.forName("Main");
        Method method = type.getMethod("hello", String.class);
        System.out.println(method.invoke(null, name));

        List<String> names = new ArrayList<>();
        for (Method declared : type.getDeclaredMethods()) {
            names.add(declared.getName());
        }
        names.sort(null);
        System.out.println(names);

        URI uri = new URI(address);
        System.out.println(uri.getScheme() + " " + uri.getHost() + " " + uri.getPath());
        System.out.println(Arrays.toString(uri.getQuery().split("&")));
    }
}
