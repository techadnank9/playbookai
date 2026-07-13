# Kylon workspace bootstrap (GrowthMasters GTM track)

Do these once. Playbook AI's local engine already has your Nimble key in `.env`.

## 1. Credits
Open: https://app.kylon.io/c/q_rBaZ_kIMG8yUdV2FpiISm-rfosOZkj

## 2. Channel
Create `#gtm-playbook` (or similar) and invite **Playbook**.

## 3. Nimble secret (in Kylon)
Message Playbook:
```
Help me store a secret called NIMBLE_API_KEY
```
Paste the same Nimble key when the secret window opens.

## 4. Gmail
Playbook → **Connections** → **Connect** on Gmail.

## 5. Persona
Paste `kylon/PERSONA.md` into Playbook → **Persona**.

## 6. Smoke test (inside Kylon)
```
Use the Nimble API to search for "top AI startups in San Francisco 2026" and show me the results.
```

## 7. Full Playbook AI run (local → paste into channel)
```bash
cd /Users/adnan/Documents/ensemble
python3 run_kylon.py https://www.notion.com/
```
Copy the markdown output into `#gtm-playbook`.

Optional send (needs `KYLON_API_KEY=pak_...` in `.env`):
```bash
python3 run_kylon.py https://www.notion.com/ --send
```
