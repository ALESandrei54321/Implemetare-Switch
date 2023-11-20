# TEMA RETELE LOCALE - IMPLEMANTAREA SWITCH

----------Descriere----------

Scopul acestei teme a fost de implementare a functionalitatilor specifice unui switch, acestea fiind tabela de comutare (CAM), functionalitatea pe VLAN-uri si o forma simplificata de STP (Spanning Tree Protocol), motivul de la baza acestei teme fiind intelegerea complexitatii unui element de la nivelul legatura de date.

----------Functionalitate----------

Codul din cadrul fisierului switch.py are implementat toate functionalitatile precizate mai sus.

----------Tabela de comutare----------

Tabela de comutare este implementat prin dictionarul MAC_table, unde adresele MAC ale dispozitivelor sunt asociate cu porturile corespunzatoare.

----------VLAN----------

Switch-ul implementeaza suport pentru VLAN-uri. Interfetele sunt configurate cu tipurile de cabluri specificate in fisierul de configurare, iar procesul de invatare al switch-ului se realizeaza in functie de tipul acestora. Tratarea corecta a VLAN-urilor este asigurata de verificarea si manipularea etichetei VLAN.

----------STP----------

Implementarea STP este simplificata si se realizeaza prin 'intelegerea' dintre switch-uri pentru stabilirea Root Bridge-ului iar apoi prin procesarea pachetelor BPDU trimise de catre acesta la fiecare secunda.

----------Functii/structuri auxiliare----------

Pentru simplificarea procesului de trimitere de pachete am creat functia forward_frame care are acelasi rol ca send_to_link, doar ca este mai usor de utilizat.

Pentru parsarea informatilor din cadrul fisierelor de configurare am creat functia parse_switch_config care se ocupa de initializarea datelor necesare despre tipul legaturilor din topologia noastra.
