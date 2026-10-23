// broken: semantic
import java.util.ArrayList;
import java.util.List;

public class TypeMismatch {
    static int length(String text) {
        return text.length();
    }

    public static void main(String[] args) {
        List<String> words = new ArrayList<>();
        words.add("слово");
        int size = words.get(0);
        String number = length("abc");
        System.out.println(size + number + undefinedName);
    }
}
