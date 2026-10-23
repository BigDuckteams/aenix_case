// broken: syntax
import java.util.ArrayList;
import java.util.List;

public class UnbalancedBraces {
    static List<Integer> evens(int limit) {
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < limit; i++) {
            if (i % 2 == 0) {
                result.add(i);
            }
        return result;
    }

    static int sum(List<Integer> values) {
        int total = 0;
        for (int v : values) {
            total += v;
        }
        return total;
    }

    public static void main(String[] args) {
        System.out.println(sum(evens(10)));
    }
}
