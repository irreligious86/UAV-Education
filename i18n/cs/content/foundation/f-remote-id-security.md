---
id: f-remote-id-security
title: "Remote ID a zabezpečení stroje: vysílání, podpis MAVLink, ochrana firmwaru"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · MAVLink 2
status: published
tags:
  - Remote ID
  - zabezpečení
  - MAVLink signing
  - firmware
related:
  - f-regulations
  - mav-routing
  - nav-resilience
  - link-elrs
  - mav-component
next:
  - mav-component
source: content/foundation/f-remote-id-security.md
source_hash: 654aac96c08a
---

## summary
Dvě otázky, které musí inženýr bezpilotních letadel vyřešit před sériovým provozem: „vidí letecký úřad, kdo letí“ a „může můj stroj řídit někdo cizí“. První je Remote ID: stroj za letu vysílá svůj identifikátor, souřadnice a polohu pilota a v řadě zemí je to povinná podmínka létání. Druhá je plocha útoku (attack surface): RC spoj, telemetrie MAVLink, GNSS, síť companion počítače a samotný firmware. Modul rozebírá, co a jak Remote ID vysílá, jak se připojuje k ArduPilotu a PX4, jak funguje podpis MAVLink 2 a co *nedělá*, kde je companion otevřený a jak se firmware chrání před podvržením. Laboratorní úloha: zapnout podpis v SITL a dokázat, že nepodepsané příkazy se zahazují.

## theory
### Remote ID: co se vysílá
Remote ID (Drone ID) je všesměrové vysílání ze stroje, které přijme běžný chytrý telefon poblíž. Podle normy ASTM F3411 (vycházejí z ní pravidla USA) a evropské normy (ASD-STAN EN 4709-002) zprávy obsahují:
- identifikátor stroje (sériové číslo) a/nebo registrační číslo provozovatele;
- souřadnice, výšku, rychlost a kurz stroje;
- souřadnice vysílačky/pilota (nebo místa vzletu – podle pravidel);
- časovou značku a stav (včetně nouzového).

Přenos zajišťuje Bluetooth (4 legacy a 5 long range) a Wi-Fi (NAN a Beacon). Je to **všesměrové vysílání** bez spojení se serverem, proto funguje i bez internetu.

### Pro koho a kdy je povinné
V USA platí pravidlo FAA Part 89 (od března 2024 povinné pro většinu letů): vestavěné Remote ID, externí modul („maják“), nebo lety jen ve zvlášť vyhrazených zónách (FRIA). V EU je přímé Remote ID součástí požadavků na třídy C1–C3 a na specifickou kategorii, k tomu registrační číslo provozovatele. V jiných zemích jsou pravidla vlastní a mění se – ověřte si je před prvním letem u svého leteckého úřadu; výchozím bodem je modul `f-regulations`.

### Remote ID na ArduPilotu a PX4
- **Modul přes MAVLink nebo DroneCAN** si bere souřadnice od autopilotu a vysílá je. Hotové moduly (Cube ID, Holybro a další s podporou OpenDroneID) nebo otevřený **ArduRemoteID** – firmware od ArduPilotu pro desky ESP32-S3/ESP32-C3, které se připojují přes MAVLink nebo DroneCAN (pro CAN je potřeba externí transceiver).
- **Samostatný maják** – s vlastní GPS a baterií; k autopilotu se nepřipojuje.
- **ArduPilot**: subsystém OpenDroneID – `DID_ENABLE`, port `DID_MAVPORT` nebo `DID_CANDRIVER`, `DID_OPTIONS`. Pro certifikované konfigurace se používá zvláštní sestavení firmwaru s ochranou proti změnám a s kontrolami před vzletem: bez funkčního Remote ID stroj nejde armovat. ArduRemoteID umí zablokovat změnu svých parametrů (změny jen podepsanými příkazy).
- **PX4**: podporuje zprávy OpenDroneID a externí moduly; zapnutí a kontroly najdete v oddílu Remote ID dokumentace své verze.
- Zprávy MAVLink: rodina `OPEN_DRONE_ID_*` (`OPEN_DRONE_ID_BASIC_ID`, `_LOCATION`, `_SYSTEM`, `_OPERATOR_ID`); souřadnice pilota posílá modulu pozemní stanice (`OPEN_DRONE_ID_SYSTEM`).

### Plocha útoku
| Kanál | Hrozba | Ochrana |
|---|---|---|
| RC spoj | cizí vysílač se stejným bindingem, rušení (jamming) | jedinečná binding phrase v ELRS (je to identifikátor páru, ne šifrování), promyšlený failsafe |
| Telemetrie MAVLink | cizí příkazy: změna režimu, disarm, nahrání mise | podpis MAVLink 2, samostatné klíče pro každý stroj, MAVLink 1 vypnutý na rádiových portech |
| GNSS | rušení (jamming), spoofing | kontroly EKF, navigace bez GNSS, posouzení podle `nav-resilience` |
| Companion | otevřená Wi-Fi, výchozí heslo, SSH, UDP telemetrie do celého segmentu, DDS bez ochrany | klíče SSH místo hesel, firewall, telemetrie jen na potřebnou adresu, omezení discovery a SROS2 |
| Firmware | podvržení firmwaru nebo parametrů | podepsaný firmware a zabezpečený bootloader, správa verzí parametrů |

### Podpis MAVLink 2: jak funguje
- Stroj a pozemní stanice mají společný **tajný klíč o délce 32 bajtů**. Ke každému paketu se přidává 13 bajtů: link ID (1 bajt), časová značka (6 bajtů, v jednotkách 10 µs od 1. ledna 2015) a podpis (6 bajtů – prvních 48 bitů SHA-256 z klíče, hlavičky, datové části, CRC, link ID a časové značky).
- Časová značka musí růst – opakování zaznamenaného paketu (replay) se zahodí.
- **ArduPilot**: na portech s MAVLink 2 se příkazy bez správného podpisu neprovedou, telemetrie směrem dolů jde jako dřív. USB **chráněno není** – přes USB lze klíč změnit nebo smazat (fyzický přístup = plný přístup). MAVLink 1 podpis nemá – rádiové porty se přepínají na MAVLink 2 (`SERIALn_PROTOCOL = 2`). V Mission Planneru: Setup → Advanced → MAVLink Signing.
- **Podpis je autentizace, ne šifrování.** Provoz zůstává čitelný: souřadnice, misi a parametry vidí každý, kdo má přijímač. Šifrování se řeší na úrovni rádia (například AES v některých telemetrických modemech, klíč ve WFB-ng) nebo pomocí VPN nad IP.

### Companion: síť je hlavní díra
- Raspberry Pi nebo Jetson s výchozím heslem, SSH s přihlášením heslem a přístupovým bodem Wi-Fi je to první, co útočník najde.
- `mavlink-router`/MAVProxy, které vysílají telemetrii na broadcast adresu, ji dávají všem v síti – zadávejte konkrétní adresu pozemní stanice.
- ROS 2 ve výchozím nastavení hledá účastníky pomocí multicastu v celé síti. `ROS_DOMAIN_ID` systémy odděluje, ale **nechrání**; v Jazzy omezí `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` discovery na samotný počítač. Autentizaci a šifrování DDS zajišťuje SROS2 (DDS Security).

### Firmware a parametry
- ArduPilot podporuje **podepsaný firmware**: do bootloaderu se vloží veřejný klíč, firmware se podepisuje soukromým; nepodepsaný firmware bootloader nespustí. Klíč se uchovává mimo repozitář, postup je popsán v dokumentaci Secure Firmware.
- Parametry jsou také bezpečnostní konfigurace: referenční soubor parametrů uchovávejte v gitu (modul `eng-ci-configs`) a před letem ho porovnejte se strojem.

{{diagram:security-surface|Kanály útoku na stroj a jejich ochrana: binding a failsafe pro RC, podpis MAVLink 2 pro telemetrii, kontroly EKF pro GNSS, firewall a SROS2 pro companion, podepsaný firmware.}}

## practice
### Krok 1. Mapa vlastního stroje
Tabulka z teorie pro váš stroj: jaké kanály má a co je teď otevřené (port, protokol, heslo, adresa). Označte tři nejnebezpečnější položky.

### Krok 2. Podpis v SITL
Spusťte ArduPilot SITL s MAVProxy. Zapněte podpis:
```text
signing setup mysecretphrase
```
MAVProxy předá klíč autopilotu a začne své pakety podepisovat. Potom zkuste ze samostatného skriptu bez klíče změnit režim:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("udpin:0.0.0.0:14551"); m.wait_heartbeat()
m.set_mode("GUIDED")                       # bez podpisu
print(m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3))
```
Skript připojte přes `--out udp:127.0.0.1:14551` u MAVProxy nebo přes samostatný port SITL. Pokud příkaz přes MAVProxy projde, je to očekávané: MAVProxy je připojen k SERIAL0 SITL (`tcp:127.0.0.1:5760`) a kanál 0 považuje ArduPilot za chráněný (jako USB) a přijímá na něm nepodepsané pakety – připojte skript přímo k portu SITL (`tcp:127.0.0.1:5763`, SERIAL2). Zapište, zda byl režim bez klíče přijat, a potom s klíčem:
```python
import hashlib
key = hashlib.sha256(b"mysecretphrase").digest()   # MAVProxy vytváří klíč stejně
m.setup_signing(key, sign_outgoing=True)
```
Ověřte, že s klíčem se režim změní. Zvlášť ověřte, že telemetrie směrem dolů je čitelná i bez klíče – podpis nešifruje.

### Krok 3. Companion
Na vlastním companion počítači (nebo ve virtuálním stroji): `ss -tulpn` ukáže, které porty naslouchají a na kterých adresách. Zavřete, co je navíc, SSH povolte jen s klíčem, telemetrii posílejte na konkrétní adresu pozemní stanice. U ROS 2 ověřte `ros2 node list` z jiného počítače ve stejné síti před nastavením `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` a po něm.

### Krok 4. Remote ID (pokud máte modul)
Připojte modul (hotový nebo ArduRemoteID na ESP32-S3) přes MAVLink, zapněte `DID_ENABLE` a nastavte port. Chytrým telefonem s aplikací OpenDroneID ověřte, že jsou vidět identifikátor a souřadnice stroje i pilota. Pokud modul nemáte, sestavte podle pravidel své země seznam požadavků na svůj stroj a způsob, jak je splnit.

Laboratorní úloha je splněna, když je mapa kanálů sestavená, v SITL je dokázáno, že nepodepsaný příkaz se neprovede a podepsaný se provede, otevřené porty companion počítače jsou vypsané a nepotřebné zavřené a k Remote ID existuje ověření vysílání nebo seznam požadavků s řešením.

## diagnostics
- **Příznak:** po zapnutí podpisu pozemní stanice stroj „vidí“, ale příkazy neprocházejí
  - Možná příčina: klíč v pozemní stanici se neshoduje s klíčem autopilotu.
  - Co udělat: zvolte v pozemní stanici stejný klíč; při ztrátě klíč změňte nebo smažte přes USB.
- **Příznak:** podpis je zapnutý, ale cizí pozemní stanice stroj přesto řídí
  - Možná příčina: rádiový port běží v MAVLink 1, příkaz přišel přes USB nebo přes uzel, který podepisuje za všechny (router s klíčem).
  - Co udělat: `SERIALn_PROTOCOL = 2` na rádiových portech, zkontrolujte řetězec směrování, klíč mají mít jen ti, kdo stroj řídí.
- **Příznak:** stroj nejde armovat a hlásí chybu Remote ID
  - Možná příčina: modul není připojen nebo nedostal souřadnice pilota, chybí spojení s pozemní stanicí, není zadáno ID provozovatele.
  - Co udělat: zkontrolujte spojení s modulem, data `OPEN_DRONE_ID_SYSTEM` z pozemní stanice a parametry modulu.
- **Příznak:** telemetrii z companion počítače vidí všichni v síti
  - Možná příčina: výstup na broadcast adresu, discovery ROS 2 v celé síti.
  - Co udělat: adresa pozemní stanice místo broadcastu, firewall, omezení discovery, SROS2.
- **Příznak:** po aktualizaci firmware na zabezpečeném bootloaderu nenaběhne
  - Možná příčina: firmware není podepsaný nebo je podepsaný jiným klíčem.
  - Co udělat: podepište ho vlastním klíčem podle postupu Secure Firmware.

## references
- ArduPilot — MAVLink2 signing | https://ardupilot.org/copter/docs/common-MAVLink2-signing.html | primary | A
- MAVLink — Message signing | https://mavlink.io/en/guide/message_signing.html | primary | A
- ArduPilot — Remote ID (OpenDroneID) | https://ardupilot.org/copter/docs/common-remoteid.html | primary | A
- ArduRemoteID — open Remote ID firmware | https://github.com/ArduPilot/ArduRemoteID | primary | A
- FAA — Remote Identification of drones | https://www.faa.gov/uas/getting_started/remote_id | primary | A
- ROS 2 — Security (SROS2) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Security.html | primary | A

## checklist
- Umím vysvětlit, co Remote ID vysílá a kterými rádiovými kanály
- Vím, kde hledat požadavky své země, a znám způsoby, jak je splnit
- Umím připojit modul Remote ID k ArduPilotu přes MAVLink nebo DroneCAN
- Umím vyjmenovat kanály útoku na stroj a ochranu každého z nich
- Umím zapnout podpis MAVLink 2 a chápu, že nešifruje
- Umím uzavřít síť companion počítače a omezit discovery ROS 2
- Vím, co je podepsaný firmware a zabezpečený bootloader
