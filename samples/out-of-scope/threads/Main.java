import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** Вне рамок кейса: потоки, java.util.concurrent, synchronized. Вывод детерминирован за счёт join. */
public class Main {
    private static int shared;

    private static synchronized void increment() {
        shared++;
    }

    public static void main(String[] args) throws Exception {
        Scanner in = new Scanner(System.in, "UTF-8");
        int n = in.nextInt();

        Thread[] threads = new Thread[4];
        for (int i = 0; i < threads.length; i++) {
            threads[i] = new Thread(() -> {
                for (int k = 0; k < n; k++) {
                    increment();
                }
            });
            threads[i].start();
        }
        for (Thread thread : threads) {
            thread.join();
        }
        System.out.println("счётчик: " + shared);

        ExecutorService pool = Executors.newFixedThreadPool(3);
        List<Future<Long>> parts = new ArrayList<>();
        for (int part = 0; part < 3; part++) {
            final int start = part * n;
            parts.add(pool.submit(() -> {
                long sum = 0;
                for (int k = start; k < start + n; k++) {
                    sum += k;
                }
                return sum;
            }));
        }
        long total = 0;
        for (Future<Long> part : parts) {
            total += part.get();
        }
        pool.shutdown();
        System.out.println("сумма: " + total);
    }
}
