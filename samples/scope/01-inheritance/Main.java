import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

abstract class Animal {
    protected final String name;

    Animal(String name) {
        this.name = name;
    }

    abstract String sound();

    String intro() {
        return name + " говорит " + sound();
    }
}

class Dog extends Animal {
    Dog(String name) {
        super(name);
    }

    @Override
    String sound() {
        return "гав";
    }
}

class Puppy extends Dog {
    Puppy(String name) {
        super(name);
    }

    @Override
    String sound() {
        return super.sound() + "-гав";
    }

    @Override
    String intro() {
        return "Щенок " + super.intro();
    }
}

class Cat extends Animal {
    Cat(String name) {
        super(name);
    }

    @Override
    String sound() {
        return "мяу";
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        List<Animal> animals = new ArrayList<>();
        while (in.hasNext()) {
            String kind = in.next();
            String name = in.next();
            switch (kind) {
                case "dog":
                    animals.add(new Dog(name));
                    break;
                case "puppy":
                    animals.add(new Puppy(name));
                    break;
                default:
                    animals.add(new Cat(name));
            }
        }
        for (Animal animal : animals) {
            System.out.println(animal.intro());
        }
    }
}
