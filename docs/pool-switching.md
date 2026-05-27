# Pool-Wechsel

## Warum wechseln?

- Pool 1 überlastet / langsam → auf Pool 2 oder 3 ausweichen
- 412 Suspended auf einem Pool → Retry trifft evtl. anderen Pool
- Loadbalancing manuell steuern

## Wechseln

Einfach anderen Installer laufen lassen:

```bash
# Bisher: Pool 1
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool1.sh | bash

# Jetzt: Pool 2
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool2.sh | bash
```

Der Installer überschreibt `~/.hermes/config.yaml` mit der neuen Pool-URL. Kein Restart nötig.

## Verifizierung

```bash
# Aktueller Pool
grep "base_url" ~/.hermes/config.yaml

# Sollte zeigen:
#   base_url: https://sinatorpoolX.delqhi.com/inference/v1
```

## Multi-Pool gleichzeitig?

Nein — Hermes Config erlaubt nur einen `custom_providers` Eintrag mit Namen `fireworks`. Der Complete-Installer installiert alle 3 nacheinander, aber nur der letzte "gewinnt".

Workaround für Multi-Pool: Cronjob oder Script das periodisch `config.yaml` rotiert.
