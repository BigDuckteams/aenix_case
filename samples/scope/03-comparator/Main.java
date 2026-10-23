import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Scanner;

class Person {
    final String name;
    final int age;
    final double salary;

    Person(String name, int age, double salary) {
        this.name = name;
        this.age = age;
        this.salary = salary;
    }

    String getName() {
        return name;
    }

    int getAge() {
        return age;
    }

    double getSalary() {
        return salary;
    }

    @Override
    public String toString() {
        return name + "(" + age + ", " + salary + ")";
    }
}

class ByNameLength implements Comparator<Person> {
    @Override
    public int compare(Person a, Person b) {
        return Integer.compare(a.getName().length(), b.getName().length());
    }
}

public class Main {
    static void show(String title, List<Person> people) {
        System.out.println(title + ": " + people);
    }

    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        List<Person> people = new ArrayList<>();
        while (in.hasNext()) {
            people.add(new Person(in.next(), in.nextInt(), in.nextDouble()));
        }
        List<Person> copy = new ArrayList<>(people);

        copy.sort(Comparator.comparing(Person::getName));
        show("по имени", copy);
        copy.sort(Comparator.comparingInt(Person::getAge).thenComparing(Person::getName));
        show("по возрасту, затем имени", copy);
        copy.sort(Comparator.comparingDouble(Person::getSalary).reversed());
        show("по зарплате убыв.", copy);
        copy.sort((a, b) -> b.getAge() - a.getAge());
        show("лямбда по возрасту убыв.", copy);
        copy.sort(new ByNameLength().thenComparing(Comparator.comparing(Person::getName)));
        show("по длине имени", copy);
        copy.sort(Comparator.comparing(Person::getName, Comparator.reverseOrder()));
        show("имя в обратном порядке", copy);
    }
}
