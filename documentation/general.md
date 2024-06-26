# General application principles and data flow

1. Launching application
2. Downloading data from database - to implement
3. Inserting data from step 2 to .json file. - to implement
4. Initial validation.
5. Generation of device data class instances
6. Managment


###### Description of classes #####

#### Classes related to the definition of devices ####

## Energy class ##

1. This is class from which all classes of power generating equipment will inherit. It will have the following fields:

# Data from database

    - id
    - name 
    - max_output
    - current_output rzeczywista moc na wyjściu
    - switch_status
    - device status

    - minimalna
    - priorytet

# Other data

    - is_valid

# Questions

    - parametr dotyczący regulacji???

2. Methods that this class has:

    - validate
    - create_instance
    - activate: with a starting parameter that sets the output (po zastanowieniu raczej nie chcę mieć do tego dostępu i trzeba ogarnąć jakąś wydajność, która będzie miała wpływ na wyjście) co na wejściu???
    - deactivate
    - increase: bierze aktualne wyjście i dodaje jakąś ilość i porównuje z maksymalnym możliwym wyjściem
    - decrease: na podobnej zasadzie
    - try methods: call x times with delay associated methods, for example: try_increase_output(self, amount, attempts=3, delay=1)
    - metody zwracające wartośći z pól

## BESS class ##

1. This is the class for battery-type devices. It will have the following fields:

# Data from database

    - id
    - name 
    - capacity
    - charge_level
    - switch_status

# Other data

    - status
    - is_valid

# Questions

    - parametr dotyczący regulacji???

2. Methods that this class has:

    - validate
    - create_instance
    - activate
    - deactivate
    - charge: co na wejściu??
    - discharge
    - try methods: call x times with delay associated methods, for example: try_increase_output(self, amount, attempts=3, delay=1)
    - metody zwracające wartośći z pól

#### Classes related to the managment ####

## Set device and microgrid class ##

1. Klasy mające na celu dodawanie urządzęń z pliku .json do mikrosieci. Do przerobienia, bo zmianach wprowadzonych z dodawaniem urządzęń i walidacją z pliku .json. 

## Energy manager class ##

1. Główna klasa zarządzająca, która sprawdza najważniejszy warunek, czyli czy jesteśmy w sytuacji nadwyżki czy deficytu mocy. Na bazie tego uruchamiane są odpowiednie algorytmy.

## Energy surplus manager class ##

1. Klasa zarządzająca nadwyżką mocy.

## Energy deficit manager class ##

1. Klasa zarządzająca deficytem mocy.

#### Other classes ####

## OSD contract ##

1. Klasa zawierająca stałe, które zostały zakontraktowane z dostarczycielem energii.

## OSD ##

1. Klasa zawierająca informacje bieżące związane z dostawcą, takie jak: aktualna taryfa, zsuomowana sprzedaż (czy możemy sprzedawać), zsumowana bądź chwilowa moc (czy możemy kupować)

## Klasa zarządzająca pobraniem danych z bazy i zapisaniem ich do pliku .json - do zaimplementowania ##