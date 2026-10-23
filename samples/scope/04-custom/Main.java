import java.util.Scanner;

class BankException extends Exception {
    private static final long serialVersionUID = 1L;

    BankException(String message) {
        super(message);
    }

    BankException(String message, Throwable cause) {
        super(message, cause);
    }
}

class InsufficientFundsException extends BankException {
    private static final long serialVersionUID = 1L;
    private final int shortage;

    InsufficientFundsException(int shortage) {
        super("не хватает " + shortage);
        this.shortage = shortage;
    }

    int getShortage() {
        return shortage;
    }
}

class FrozenAccountError extends RuntimeException {
    private static final long serialVersionUID = 1L;

    FrozenAccountError(String message) {
        super(message);
    }
}

class Account {
    private int balance;
    private boolean frozen;

    Account(int balance) {
        this.balance = balance;
    }

    void freeze() {
        frozen = true;
    }

    void withdraw(int amount) throws BankException {
        if (frozen) {
            throw new FrozenAccountError("счёт заморожен");
        }
        if (amount <= 0) {
            throw new BankException("сумма должна быть положительной", new IllegalArgumentException("amount=" + amount));
        }
        if (amount > balance) {
            throw new InsufficientFundsException(amount - balance);
        }
        balance -= amount;
    }

    int getBalance() {
        return balance;
    }
}

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in, "UTF-8");
        Account account = new Account(in.nextInt());
        while (in.hasNext()) {
            String command = in.next();
            if (command.equals("freeze")) {
                account.freeze();
                continue;
            }
            int amount = in.nextInt();
            try {
                account.withdraw(amount);
                System.out.println("снято " + amount + ", остаток " + account.getBalance());
            } catch (InsufficientFundsException e) {
                System.out.println("недостаточно средств: " + e.getMessage() + " (" + e.getShortage() + ")");
            } catch (BankException e) {
                System.out.println("ошибка банка: " + e.getMessage() + ", причина: " + e.getCause().getMessage());
            } catch (FrozenAccountError e) {
                System.out.println("отказ: " + e.getMessage());
            }
        }
    }
}
