"""Jeu de cartes à collectionner : version console.

Lancer avec :  python jeu.py
La logique est dans moteur.py, les cartes dans cartes.json,
la progression dans sauvegarde.json (cette sauvegarde est séparée de celle du site).
"""
import json
import time
from pathlib import Path

from moteur import (BOUTIQUE, INTERVALLE_SECONDES, ORDRE, STOCK_MAX, acheter, boosters_disponibles,
                    etat_initial, ouvrir_booster, synchroniser)

DOSSIER = Path(__file__).parent
FICHIER_CARTES = DOSSIER / "cartes.json"
FICHIER_SAUVEGARDE = DOSSIER / "sauvegarde.json"
SYMBOLES = {
    "commune": "⚪",
    "rare": "🔵",
    "super rare": "🟣",
    "ultra rare": "🔴",
    "légendaire": "🟡",
    "secrète": "💠",
}
FINITIONS = {"brillante": "✦ brillante", "arc-en-ciel": "🌈 arc-en-ciel"}


def maintenant():
    return int(time.time() * 1000)


def charger_cartes():
    with open(FICHIER_CARTES, encoding="utf-8") as f:
        return json.load(f)


def charger_sauvegarde():
    if FICHIER_SAUVEGARDE.exists():
        with open(FICHIER_SAUVEGARDE, encoding="utf-8") as f:
            return synchroniser(json.load(f), maintenant())
    return etat_initial(maintenant())


def sauvegarder(etat):
    with open(FICHIER_SAUVEGARDE, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=2)


def afficher_carte(carte):
    marque = "  ✨ NOUVELLE" if carte["nouvelle"] else ""
    if carte["nouvelle_finition"]:
        marque = "  ✨ NOUVELLE FINITION"
    fin = f"  {FINITIONS[carte['finition']]}" if carte["finition"] in FINITIONS else ""
    gain = f"  +{carte['pieces']} pièces" if carte["pieces"] else ""
    print(f"  {SYMBOLES[carte['rarete']]} {carte['nom']}  [{carte['rarete']}]{fin}{marque}{gain}")


def afficher_collection(cartes, etat):
    possedees = etat["collection"]
    print(f"\n=== Collection : {len(possedees)}/{len(cartes)} cartes ===")
    for rarete in ORDRE:
        de_cette_rarete = [c for c in cartes if c["rarete"] == rarete]
        n = sum(1 for c in de_cette_rarete if str(c["id"]) in possedees)
        print(f"{SYMBOLES[rarete]} {rarete.upper()} : {n}/{len(de_cette_rarete)}")


def afficher_stats(etat):
    print(f"\nBoosters ouverts : {etat['boosters_ouverts']}")
    print(f"Pièces : {etat['monnaie']}")
    print(f"Boosters gratuits : {etat['stock']}/{STOCK_MAX} · achetés : {etat['achetes']} · ultra rare garantie : {etat['achetes_ur']}")
    if etat["stock"] < STOCK_MAX:
        reste = max(0, etat["horloge"] + INTERVALLE_SECONDES * 1000 - maintenant()) // 1000
        print(f"Prochain booster gratuit dans {reste // 60:02d}:{reste % 60:02d}")


def boutique(etat):
    print(f"\n--- BOUTIQUE ({etat['monnaie']} pièces) ---")
    for i, o in enumerate(BOUTIQUE, 1):
        print(f"{i}. {o['nom']} : {o['prix']} pièces")
    choix = input("Numéro à acheter (Entrée pour revenir) > ").strip()
    if choix.isdigit() and 1 <= int(choix) <= len(BOUTIQUE):
        erreur = acheter(etat, BOUTIQUE[int(choix) - 1]["id"], maintenant())
        print(erreur or "Acheté !")


def main():
    cartes = charger_cartes()
    etat = charger_sauvegarde()

    while True:
        synchroniser(etat, maintenant())
        print("\n--- MENU ---")
        print(f"1. Ouvrir un booster ({boosters_disponibles(etat)} disponibles)")
        print(f"2. Ouvrir un booster ultra rare garanti ({etat['achetes_ur']})")
        print("3. Boutique")
        print("4. Voir ma collection")
        print("5. Statistiques")
        print("6. Quitter")
        try:
            choix = input("> ").strip()
        except EOFError:
            break

        if choix in ("1", "2"):
            try:
                tirage, _ = ouvrir_booster(cartes, etat, maintenant(), "normal" if choix == "1" else "ur")
            except ValueError as e:
                print(e)
                continue
            print("\nOuverture du booster...")
            for carte in tirage:
                afficher_carte(carte)
        elif choix == "3":
            boutique(etat)
        elif choix == "4":
            afficher_collection(cartes, etat)
        elif choix == "5":
            afficher_stats(etat)
        elif choix == "6":
            break
        sauvegarder(etat)

    sauvegarder(etat)
    print("À bientôt !")


if __name__ == "__main__":
    main()
