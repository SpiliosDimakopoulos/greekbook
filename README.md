# greekbook

Ένα εργαλείο που μετατρέπει Markdown σε καλοτυπωμένα βιβλία PDF, με ιδιαίτερη φροντίδα για την ελληνική πεζογραφία — σωστός συλλαβισμός, ελληνικά εισαγωγικά «σαν αυτά», αυτόματος πίνακας περιεχομένων, και έτοιμα θέματα εμφάνισης.

---

## Τοπική εκτέλεση

```bash
pip install -r requirements.txt
python run.py serve mybook/
```

Ανοίγει browser-tab με: editor ανά κεφάλαιο, κουμπί **Build PDF**, inline προεπισκόπηση PDF, export EPUB.

---

## Deploy στο Fly.io

### 1. Εγκατάσταση flyctl

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Δημιούργησε την εφαρμογή

```bash
fly apps create greekbook-spilios
```

> Το όνομα πρέπει να ταιριάζει με το `app` στο `fly.toml`.

### 3. Δημιούργησε το persistent volume

```bash
fly volumes create greekbook_data --region ams --size 1
```

> Το volume αποθηκεύει το βιβλίο σου μεταξύ restarts. Γίνεται **μία φορά μόνο**.

### 4. Deploy

```bash
fly deploy
```

Αυτό κάνει build το Docker image, το ανεβάζει, και εκκινεί το app. Μετά:

```
https://greekbook-spilios.fly.dev
```

### Επόμενα deploys (μετά από αλλαγές)

```bash
fly deploy
```

### Χρήσιμες εντολές

```bash
fly logs          # Live logs
fly status        # Κατάσταση machine
fly ssh console   # Shell μέσα στο container
fly volumes list  # Δες τα volumes
```

---

## Θέματα εμφάνισης

| Theme      | Ύφος                        |
|------------|-----------------------------|
| `sepia`    | Vintage, serif, ζεστό       |
| `clean`    | Μοντέρνο, sans-serif, λιτό  |
| `academic` | Σοβαρό, ακαδημαϊκό         |

---

## Δομή project/folder

```
greekbook/           ← Python package
  web/index.html     ← Single-page UI
  fonts/             ← Ενσωματωμένες γραμματοσειρές
  themes/            ← PDF themes (sepia, clean, academic)
examples/            ← Demo βιβλία (φορτώνονται στο /data στο Fly)
Dockerfile
fly.toml
entrypoint.sh        ← Αρχικοποίηση volume + εκκίνηση server
requirements.txt
run.py
```

> **Σημείωση:** Στο Fly.io τα δεδομένα (βιβλίο, παραδείγματα) αποθηκεύονται στο volume `/data` και διατηρούνται μεταξύ deploys.
