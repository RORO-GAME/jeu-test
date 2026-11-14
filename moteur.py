"""Moteur du jeu de cartes : la logique, sans aucun affichage.

Ce fichier est utilisé deux fois, sans changement :
- par jeu.py, la version console ;
- par index.html, la version web (Python tourne dans le navigateur via Pyodide).
"""
import json
import random

# ----------------------------------------------------------------------
# RÉGLAGES : c'est ici que tu joues avec l'équilibrage
# ----------------------------------------------------------------------
# Chance (en %) qu'UNE carte tirée soit de cette rareté. La commune, c'est le reste.
# Dans un booster de 3 cartes, la chance d'avoir au moins une carte d'une rareté est donc
# un peu moins de 3 fois plus grande (la page Infos du site la calcule pour toi).
_TAUX = {
    "rare": 20,
    "super rare": 6,
    "ultra rare": 1.8,
    "légendaire": 0.5,
    "secrète": 0.05,
}
RARETES = {"commune": round(100 - sum(_TAUX.values()), 4), **_TAUX}
ORDRE = list(RARETES)  # de la plus commune à la plus rare

# Le petit code affiché dans le coin de chaque carte
CODES = {
    "commune": "C",
    "rare": "R",
    "super rare": "SR",
    "ultra rare": "UR",
    "légendaire": "L",
    "secrète": "S",
}

TAILLE_BOOSTER = 3            # nombre de cartes par booster

# Garanties, éteintes pour que les taux ci-dessus soient les vrais taux.
# Pour les rallumer : GARANTIE_DERNIERE = "rare" (la dernière carte est au moins "rare"),
# PITIE_APRES = 8 (après 8 boosters sans carte "super rare" ou mieux, le suivant en contient une).
GARANTIE_DERNIERE = None
PITIE_APRES = None
PITIE_RARETE = "super rare"

# Finitions : chance qu'une carte tirée soit brillante ou arc-en-ciel,
# quelle que soit sa rareté (0.02 = 2 %).
CHANCE_BRILLANTE = 0.02
CHANCE_ARC_EN_CIEL = 0.005

# Monnaie : un doublon (une carte que tu as déjà) rapporte des pièces.
# Plus la carte est rare, plus elle rapporte. Une carte brillante ou arc-en-ciel
# rapporte un peu plus : la valeur est multipliée, puis arrondie.
VALEUR_DOUBLON = {
    "commune": 2,
    "rare": 5,
    "super rare": 12,
    "ultra rare": 30,
    "légendaire": 80,
    "secrète": 250,
}
BONUS_FINITION = {"normale": 1, "brillante": 1.5, "arc-en-ciel": 2}

# Les doublons ne rapportent plus de pièces tout seuls : ils restent en stock et on choisit
# de les VENDRE (la moitié de l'ancienne valeur) ou de les DÉPENSER pour monter une carte de niveau.
VALEUR_VENTE = {
    "commune": 1,
    "rare": 3,
    "super rare": 6,
    "ultra rare": 15,
    "légendaire": 40,
    "secrète": 125,
}

# Niveaux : 1 (départ), 2, 3, puis 4 = niveau max. Coût en doublons pour passer au niveau suivant.
NIVEAU_MAX = 4
COUT_NIVEAU = {   # [niveau 1 -> 2, 2 -> 3, 3 -> max]
    "commune": [3, 5, 8],
    "rare": [3, 4, 6],
    "super rare": [2, 3, 5],
    "ultra rare": [2, 3, 4],
    "légendaire": [1, 2, 3],
    "secrète": [1, 1, 2],
}
BONUS_POINTS_NIVEAU = [0, 0.5, 1.5, 3]   # points du classement en plus (fois les points de la carte), par niveau

# Cartes fantômes : dans cartes.json, une carte avec "fantome": true. Elle se révèle peu à peu :
# chaque exemplaire tiré découvre une part de l'image (mosaïque). REQUIS = exemplaires pour tout révéler.
REQUIS_FANTOME = {
    "commune": 6,
    "rare": 5,
    "super rare": 4,
    "ultra rare": 3,
    "légendaire": 3,
    "secrète": 2,
}

# Classement : chaque carte obtenue (doublons compris) rapporte des points, plus ou moins selon sa rareté,
# avec le même bonus de finition que les pièces. Ces points ne sont jamais affichés carte par carte :
# le site ne montre que le total (le "score") dans le classement.
POINTS = {
    "commune": 1,
    "rare": 3,
    "super rare": 10,
    "ultra rare": 30,
    "légendaire": 100,
    "secrète": 400,
}

# Boosters gratuits : un nouveau booster toutes les 15 minutes, 10 au maximum en réserve.
INTERVALLE_SECONDES = 15 * 60
STOCK_MAX = 10
BOOSTERS_DEPART = 3           # boosters offerts à la création d'un compte
MULTI_DUREE_SECONDES = 3600   # un multiplicateur gagné dure une heure

# Le compte admin : le pseudo qui a le droit de gérer les codes et d'ouvrir des boosters librement.
# (Si tu changes ce pseudo, change aussi l'adresse dans les règles Firestore : voir LISEZMOI.md.)
ADMIN_PSEUDO = "admin1234"

# Roue de la chance : un tour par jour, remis à zéro à minuit.
# "poids" = chance en % (le total fait 100). L'ordre de la liste est l'ordre sur la roue.
# Une récompense peut donner "pieces", "boosters" ou un multiplicateur "multi" (×2, ×3, ×5 : un booster gratuit
# arrive 2, 3 ou 5 fois plus vite pendant MULTI_DUREE_SECONDES).
ROUE = [
    {"id": "p10", "texte": "10 pièces", "court": "10 pièces", "poids": 25, "pieces": 10},
    {"id": "x2", "texte": "Multiplicateur ×2", "court": "×2", "poids": 20, "multi": 2},
    {"id": "p25", "texte": "25 pièces", "court": "25", "poids": 10, "pieces": 25},
    {"id": "b1", "texte": "1 booster", "court": "Booster", "poids": 20, "boosters": 1},
    {"id": "x5", "texte": "Multiplicateur ×5", "court": "×5", "poids": 5, "multi": 5},
    {"id": "p50", "texte": "50 pièces", "court": "50", "poids": 5, "pieces": 50},
    {"id": "x3", "texte": "Multiplicateur ×3", "court": "×3", "poids": 10, "multi": 3},
    {"id": "rien", "texte": "Rien du tout", "court": "Rien", "poids": 5},
]

# Boutique : "boosters" = boosters normaux ajoutés, "ur" = boosters "ultra rare garantie" ajoutés.
# Les boosters achetés ne sont pas limités par STOCK_MAX.
BOUTIQUE = [
    {"id": "unite", "nom": "1 booster", "prix": 10, "boosters": 1, "ur": 0,
     "texte": "Un booster de plus, tout de suite."},
    {"id": "x10", "nom": "10 boosters", "prix": 90, "boosters": 10, "ur": 0,
     "texte": "Dix boosters pour le prix de neuf."},
    {"id": "ur", "nom": "Booster ultra rare", "prix": 100, "boosters": 0, "ur": 1,
     "texte": "Une carte ultra rare ou mieux est garantie."},
]


# ----------------------------------------------------------------------
# État du joueur
# ----------------------------------------------------------------------
def etat_initial(maintenant=0):
    # collection : {id de la carte (texte): nombre d'exemplaires}
    # finitions  : {id de la carte (texte): {"brillante": n, "arc-en-ciel": n}}
    # monnaie    : pièces gagnées avec les doublons, moins celles dépensées
    # stock      : boosters gratuits en réserve (maximum STOCK_MAX)
    # progres    : avancement (de 0 à 1) du prochain booster gratuit ; horloge : dernier instant (en ms) calculé
    # achetes    : boosters achetés ou gagnés ; achetes_ur : boosters ultra rare garantie
    # multi      : multiplicateur en cours {"facteur": 2, "fin": instant en ms}, ou None
    # roue_jour  : le jour (texte) où la roue a été tournée pour la dernière fois
    # codes_utilises : les codes déjà utilisés
    # stat_boosters, stat_points, stat_attendu : boosters ouverts (hors tests/admin), points tirés, points qu'on en attendait en moyenne ("chance")
    # doublons   : exemplaires en stock, à vendre ou à dépenser : {id: {"normale": n, "brillante": n, "arc-en-ciel": n}}
    # niveaux    : {id: niveau de 1 à NIVEAU_MAX} (absent = niveau 1)
    # vitrine    : jusqu'à 3 cartes montrées sur le profil : [{"id": 12, "finition": "brillante"}, ...]
    return {
        "collection": {}, "finitions": {}, "monnaie": 0, "boosters_ouverts": 0, "sans_rare": 0,
        "stock": BOOSTERS_DEPART, "horloge": int(maintenant), "progres": 0.0, "achetes": 0, "achetes_ur": 0,
        "multi": None, "roue_jour": "", "codes_utilises": [],
        "stat_boosters": 0, "stat_points": 0, "stat_attendu": 0.0, "vitrine": [],
        "doublons": {}, "niveaux": {},
    }


def synchroniser(etat, maintenant):
    """Complète une ancienne sauvegarde et ajoute les boosters gagnés avec le temps qui passe
    (plus vite quand un multiplicateur est en cours)."""
    maintenant = int(maintenant)
    base = INTERVALLE_SECONDES * 1000
    if "progres" not in etat:  # sauvegarde d'avant les multiplicateurs : "horloge" était le début de l'attente
        stock = etat.get("stock", BOOSTERS_DEPART)
        debut = etat.get("horloge", maintenant)
        progres = 0.0
        if stock < STOCK_MAX and debut <= maintenant:
            gagnes = (maintenant - debut) // base
            stock = min(STOCK_MAX, stock + gagnes)
            progres = 0.0 if stock >= STOCK_MAX else (maintenant - (debut + gagnes * base)) / base
        etat["stock"], etat["progres"], etat["horloge"] = stock, progres, maintenant
    for cle, valeur in etat_initial(maintenant).items():
        etat.setdefault(cle, valeur)

    t = min(etat["horloge"], maintenant)
    progres = etat["progres"]
    if etat["stock"] >= STOCK_MAX:
        progres = 0.0  # réserve pleine : pas d'attente en cours
    else:
        for _ in range(100000):
            if t >= maintenant or etat["stock"] >= STOCK_MAX:
                break
            m = etat.get("multi")
            actif = bool(m) and t < m["fin"]
            f = m["facteur"] if actif else 1
            fin_segment = min(maintenant, m["fin"]) if actif else maintenant
            besoin = (1 - progres) * base / f
            if t + besoin <= fin_segment:
                t += besoin
                etat["stock"] += 1
                progres = 0.0
            else:
                progres += (fin_segment - t) * f / base
                t = fin_segment
        if etat["stock"] >= STOCK_MAX:
            progres = 0.0
    etat["progres"] = progres
    etat["horloge"] = maintenant
    m = etat.get("multi")
    if m and m["fin"] <= maintenant:
        etat["multi"] = None
    return etat


def attente(etat, maintenant):
    """Où en est le prochain booster gratuit ? (sans modifier l'état)"""
    maintenant = int(maintenant)
    copie = json.loads(json.dumps(etat))
    synchroniser(copie, maintenant)
    base = INTERVALLE_SECONDES * 1000
    m = copie.get("multi")
    f = m["facteur"] if m else 1
    res = {"pret": copie["stock"] > etat.get("stock", 0), "facteur": f,
           "multi_reste": max(0, m["fin"] - maintenant) if m else 0,
           "plein": copie["stock"] >= STOCK_MAX, "part": copie["progres"], "reste": 0}
    if res["plein"]:
        res["part"] = 1
        return res
    p = copie["progres"]
    besoin = (1 - p) * base / f
    if m and besoin > m["fin"] - maintenant:  # le multiplicateur s'arrête avant : le reste se fait à vitesse normale
        dispo = m["fin"] - maintenant
        besoin = dispo + (1 - (p + dispo * f / base)) * base
    res["reste"] = besoin
    return res


def boosters_disponibles(etat):
    return etat["stock"] + etat["achetes"]


def utiliser_booster(etat, mode, maintenant):
    """Retire un booster de la réserve. ValueError s'il n'y en a plus.
    Modes : "normal" (gratuit d'abord, puis acheté), "achete" (acheté seulement), "ur" (ultra rare garantie),
    "libre" et "libre_ur" (admin : rien n'est retiré)."""
    synchroniser(etat, maintenant)
    if mode in ("libre", "libre_ur"):
        return
    if mode == "achete":
        if etat["achetes"] <= 0:
            raise ValueError("Tu n'as plus de booster acheté.")
        etat["achetes"] -= 1
    elif mode == "ur":
        if etat["achetes_ur"] <= 0:
            raise ValueError("Tu n'as plus de booster ultra rare garanti.")
        etat["achetes_ur"] -= 1
    elif etat["stock"] > 0:
        if etat["stock"] >= STOCK_MAX:
            etat["horloge"] = int(maintenant)  # la réserve était pleine : l'attente repart maintenant
        etat["stock"] -= 1
    elif etat["achetes"] > 0:
        etat["achetes"] -= 1
    else:
        raise ValueError("Tu n'as plus de booster. Le prochain arrive bientôt.")


def acheter(etat, offre_id, maintenant):
    """Achète une offre de la boutique. Renvoie None si c'est réussi, sinon le message d'erreur."""
    synchroniser(etat, maintenant)
    offre = next((o for o in BOUTIQUE if o["id"] == offre_id), None)
    if offre is None:
        return "Cette offre n'existe pas."
    if etat["monnaie"] < offre["prix"]:
        return "Tu n'as pas assez de pièces."
    etat["monnaie"] -= offre["prix"]
    etat["achetes"] += offre["boosters"]
    etat["achetes_ur"] += offre["ur"]
    return None


def _donner_multi(etat, facteur, maintenant):
    duree = MULTI_DUREE_SECONDES * 1000
    m = etat.get("multi")
    if m and m["fin"] > maintenant and facteur < m["facteur"]:
        m["fin"] += duree  # un multiplicateur plus fort est déjà en cours : on le prolonge
    else:
        etat["multi"] = {"facteur": facteur, "fin": int(maintenant) + duree}


def tourner_roue(etat, jour, maintenant):
    """Un tour de roue par jour. Renvoie (erreur ou None, récompense ou None)."""
    synchroniser(etat, maintenant)  # on met le minuteur à jour avant de changer sa vitesse
    if etat["roue_jour"] == jour:
        return "Tu as déjà tourné la roue aujourd'hui. Reviens après minuit.", None
    gain = random.choices(ROUE, weights=[g["poids"] for g in ROUE])[0]
    etat["roue_jour"] = jour
    etat["monnaie"] += gain.get("pieces", 0)
    etat["achetes"] += gain.get("boosters", 0)
    if gain.get("multi"):
        _donner_multi(etat, gain["multi"], maintenant)
    return None, gain


def utiliser_code(etat, code, recompense, maintenant):
    """Utilise un code (une seule fois par joueur). Renvoie (erreur ou None, récompense reçue ou None)."""
    synchroniser(etat, maintenant)
    if code in etat["codes_utilises"]:
        return "Tu as déjà utilisé ce code.", None
    def nombre(cle):
        try:
            return max(0, min(100000, int(recompense.get(cle, 0))))
        except (TypeError, ValueError):
            return 0
    gain = {"pieces": nombre("pieces"), "boosters": nombre("boosters"), "ur": nombre("ur")}
    if not any(gain.values()):
        return "Ce code ne donne rien.", None
    etat["monnaie"] += gain["pieces"]
    etat["achetes"] += gain["boosters"]
    etat["achetes_ur"] += gain["ur"]
    etat["codes_utilises"].append(code)
    return None, gain


# ----------------------------------------------------------------------
# Logique de tirage
# ----------------------------------------------------------------------
def tirer_carte(cartes, rarete_min=None):
    """Tire une carte au hasard, avec les probabilités de RARETES."""
    debut = ORDRE.index(rarete_min) if rarete_min else 0
    # on ne garde que les raretés qui ont au moins une carte
    possibles = [r for r in ORDRE[debut:] if any(c["rarete"] == r for c in cartes)]
    if not possibles:  # aucune carte assez rare : on se rabat sur toutes celles qui existent
        possibles = [r for r in ORDRE if any(c["rarete"] == r for c in cartes)]
    rarete = random.choices(possibles, weights=[RARETES[r] for r in possibles])[0]
    return random.choice([c for c in cartes if c["rarete"] == rarete])


def valeur_doublon(rarete, finition):
    """Ancienne valeur d'un doublon (gardée pour mémoire : la vente rapporte la moitié)."""
    return int(VALEUR_DOUBLON[rarete] * BONUS_FINITION[finition] + 0.5)


def valeur_vente(rarete, finition):
    """Pièces gagnées en vendant un doublon de cette rareté et de cette finition."""
    return max(1, int(VALEUR_VENTE[rarete] * BONUS_FINITION[finition] + 0.5))


# ----------------------------------------------------------------------
# Doublons : vendre, améliorer
# ----------------------------------------------------------------------
_FINS = ("normale", "brillante", "arc-en-ciel")


def _carte(cartes, carte_id):
    for c in cartes:
        if c["id"] == carte_id:
            return c
    raise ValueError("Carte inconnue.")


def nb_doublons(etat, carte_id):
    stock = etat.get("doublons", {}).get(str(carte_id), {})
    return sum(stock.get(f, 0) for f in _FINS)


def niveau_carte(etat, carte_id):
    return etat.get("niveaux", {}).get(str(carte_id), 1)


def fantome_revelee(etat, carte):
    """False seulement pour une carte fantôme pas encore entièrement révélée."""
    if not carte.get("fantome"):
        return True
    return etat.get("collection", {}).get(str(carte["id"]), 0) >= REQUIS_FANTOME[carte["rarete"]]


def _retirer_doublons(etat, carte_id, nombre):
    """Retire `nombre` doublons, en commençant par les moins précieux. Renvoie la liste des finitions retirées."""
    stock = etat.setdefault("doublons", {}).setdefault(str(carte_id), {})
    retires = []
    for f in _FINS:
        while nombre > 0 and stock.get(f, 0) > 0:
            stock[f] -= 1
            retires.append(f)
            nombre -= 1
    if not any(stock.values()):
        etat["doublons"].pop(str(carte_id), None)
    return retires


def vendre(etat, cartes, carte_id, nombre=None):
    """Vend `nombre` doublons de la carte (tous si None). Renvoie les pièces gagnées."""
    c = _carte(cartes, carte_id)
    dispo = nb_doublons(etat, carte_id)
    if dispo <= 0:
        raise ValueError("Tu n'as pas de doublon de cette carte.")
    nombre = dispo if nombre is None else max(1, min(int(nombre), dispo))
    gain = sum(valeur_vente(c["rarete"], f) for f in _retirer_doublons(etat, carte_id, nombre))
    etat["monnaie"] = etat.get("monnaie", 0) + gain
    return gain


def vendre_tous(etat, cartes):
    """Vend tous les doublons de toutes les cartes. Renvoie (pièces gagnées, nombre de doublons vendus)."""
    gain = vendus = 0
    for cle in list(etat.get("doublons", {})):
        carte_id = int(cle)
        n = nb_doublons(etat, carte_id)
        if n > 0:
            gain += vendre(etat, cartes, carte_id, n)
            vendus += n
    return gain, vendus


def cout_niveau(rarete, niveau):
    """Doublons à dépenser pour passer au niveau suivant (None si déjà au niveau max)."""
    if niveau >= NIVEAU_MAX:
        return None
    return COUT_NIVEAU[rarete][niveau - 1]


def ameliorer(etat, cartes, carte_id):
    """Dépense des doublons pour monter la carte d'un niveau. Renvoie le nouveau niveau."""
    c = _carte(cartes, carte_id)
    cle = str(carte_id)
    if etat.get("collection", {}).get(cle, 0) <= 0:
        raise ValueError("Tu n'as pas cette carte.")
    if not fantome_revelee(etat, c):
        raise ValueError("Cette carte fantôme n'est pas encore entièrement révélée.")
    niveau = niveau_carte(etat, carte_id)
    cout = cout_niveau(c["rarete"], niveau)
    if cout is None:
        raise ValueError("Cette carte est déjà au niveau maximum.")
    if nb_doublons(etat, carte_id) < cout:
        raise ValueError(f"Il te faut {cout} doublons pour monter de niveau.")
    _retirer_doublons(etat, carte_id, cout)
    etat.setdefault("niveaux", {})[cle] = niveau + 1
    return niveau + 1


def points_carte(rarete, finition):
    return POINTS[rarete] * BONUS_FINITION[finition]


def _points_moyens(cartes):
    """(points moyens d'une carte tirée au hasard, points moyens d'une carte ultra rare ou mieux, chance d'en tirer une)."""
    presentes = {c["rarete"] for c in cartes}
    poids = {r: RARETES[r] for r in ORDRE if r in presentes}
    total = sum(poids.values()) or 1
    bonus = 1 + CHANCE_BRILLANTE * (BONUS_FINITION["brillante"] - 1) + CHANCE_ARC_EN_CIEL * (BONUS_FINITION["arc-en-ciel"] - 1)
    moyenne = sum(poids[r] / total * POINTS[r] for r in poids) * bonus
    hauts = [r for r in poids if ORDRE.index(r) >= ORDRE.index("ultra rare")]
    p_haut = sum(poids[r] for r in hauts) / total
    moy_haut = (sum(poids[r] * POINTS[r] for r in hauts) / (sum(poids[r] for r in hauts) or 1)) * bonus
    return moyenne, moy_haut, p_haut


def points_attendus(cartes, mode="normal"):
    """Points qu'un booster rapporte en moyenne : sert à comparer la chance sans favoriser les boosters ultra rare garantis."""
    moyenne, moy_haut, p_haut = _points_moyens(cartes)
    attendu = TAILLE_BOOSTER * moyenne
    if mode in ("ur", "libre_ur") and p_haut < 1:
        sans = (1 - p_haut) ** TAILLE_BOOSTER                      # chance de n'avoir aucune ultra rare : la dernière carte est remplacée
        moy_autre = (moyenne - p_haut * moy_haut) / (1 - p_haut)    # une carte qui n'est pas ultra rare ou mieux
        attendu += sans * (moy_haut - moy_autre)
    return attendu


def tirer_finition():
    x = random.random()
    if x < CHANCE_ARC_EN_CIEL:
        return "arc-en-ciel"
    if x < CHANCE_ARC_EN_CIEL + CHANCE_BRILLANTE:
        return "brillante"
    return "normale"


def tirer_booster(cartes, etat, mode="normal"):
    """Tire les cartes d'un booster et met la collection à jour (sans toucher à la réserve de boosters).

    mode "ur" (ou "libre_ur") : booster ultra rare garanti (au moins une carte ultra rare ou mieux).
    Renvoie (liste de cartes, pitie_declenchee). Chaque carte est une copie
    avec des clés en plus :
    - "finition" : "normale", "brillante" ou "arc-en-ciel"
    - "nouvelle" : True si le joueur ne possédait pas encore cette carte
    - "nouvelle_finition" : True si la carte est déjà possédée mais pas dans cette finition
    - "doublon" : True si l'exemplaire est un doublon (il part dans le stock de doublons)
    - "valeur" : pièces qu'on aurait en vendant ce doublon ; "pieces" vaut toujours 0 (rien n'est vendu tout seul)
    - "revelation" : pour une carte fantôme qui se révèle : {"avant": k, "apres": k+1, "requis": n}
    """
    etat.setdefault("finitions", {})
    etat.setdefault("monnaie", 0)
    etat.setdefault("sans_rare", 0)

    tirage = [tirer_carte(cartes) for _ in range(TAILLE_BOOSTER)]
    if GARANTIE_DERNIERE:
        tirage[-1] = tirer_carte(cartes, GARANTIE_DERNIERE)  # dernière carte : rareté minimale

    def au_moins(liste, rarete):
        seuil = ORDRE.index(rarete)
        return any(ORDRE.index(c["rarete"]) >= seuil for c in liste)

    # booster ultra rare garanti : si le tirage n'en contient pas, la dernière carte en devient une
    if mode in ("ur", "libre_ur") and not au_moins(tirage, "ultra rare"):
        tirage[-1] = tirer_carte(cartes, "ultra rare")

    # système de pitié (éteint par défaut)
    pitie = False
    if PITIE_APRES and etat["sans_rare"] >= PITIE_APRES and not au_moins(tirage, PITIE_RARETE):
        tirage[-1] = tirer_carte(cartes, PITIE_RARETE)
        pitie = True

    # on trie de la plus commune à la plus rare, pour le suspense
    tirage.sort(key=lambda c: ORDRE.index(c["rarete"]))

    # finitions, et quelles cartes sont nouvelles (un doublon dans le même booster ne l'est pas)
    etat.setdefault("doublons", {})
    deja = set(etat["collection"])
    copies = dict(etat["collection"])
    finitions_vues = {cle: set(v) for cle, v in etat["finitions"].items()}
    resultat = []
    for c in tirage:
        cle = str(c["id"])
        fin = tirer_finition()
        nouvelle = cle not in deja
        nouvelle_fin = (not nouvelle) and fin != "normale" and fin not in finitions_vues.get(cle, set())
        avant = copies.get(cle, 0)
        requis = REQUIS_FANTOME[c["rarete"]] if c.get("fantome") else 1
        extra = {}
        if c.get("fantome") and avant < requis:
            # un exemplaire de plus qui révèle une part de la carte (il n'est pas un doublon)
            doublon = False
            extra["revelation"] = {"avant": avant, "apres": avant + 1, "requis": requis}
        else:
            doublon = avant >= requis
        resultat.append({**c, "finition": fin, "nouvelle": nouvelle, "nouvelle_finition": nouvelle_fin,
                         "doublon": doublon, "valeur": valeur_vente(c["rarete"], fin) if doublon else 0, "pieces": 0, **extra})
        deja.add(cle)
        copies[cle] = avant + 1
        if fin != "normale":
            finitions_vues.setdefault(cle, set()).add(fin)

    # mise à jour de l'état
    if au_moins(tirage, PITIE_RARETE):
        etat["sans_rare"] = 0
    else:
        etat["sans_rare"] += 1
    etat["boosters_ouverts"] = etat.get("boosters_ouverts", 0) + 1
    if mode in ("normal", "achete", "ur"):  # les boosters libres (admin) ne comptent pas pour la "chance"
        etat["stat_boosters"] = etat.get("stat_boosters", 0) + 1
        etat["stat_attendu"] = etat.get("stat_attendu", 0.0) + points_attendus(cartes, mode)
        etat["stat_points"] = etat.get("stat_points", 0) + sum(points_carte(c["rarete"], c["finition"]) for c in resultat)
    for c in resultat:
        cle = str(c["id"])
        etat["collection"][cle] = etat["collection"].get(cle, 0) + 1
        if c["doublon"]:
            stock = etat["doublons"].setdefault(cle, {})
            stock[c["finition"]] = stock.get(c["finition"], 0) + 1
        if c["finition"] != "normale":
            f = etat["finitions"].setdefault(cle, {})
            f[c["finition"]] = f.get(c["finition"], 0) + 1
    return resultat, pitie


def ouvrir_booster(cartes, etat, maintenant, mode="normal"):
    """Utilise un booster de la réserve, puis le tire. ValueError s'il n'y en a plus."""
    utiliser_booster(etat, mode, maintenant)
    return tirer_booster(cartes, etat, mode)


# ----------------------------------------------------------------------
# Passerelle pour la page web (JavaScript <-> Python, en texte JSON)
# ----------------------------------------------------------------------
def reglages_web():
    return json.dumps({
        "ordre": ORDRE,
        "codes": [CODES[r] for r in ORDRE],
        "poids": [RARETES[r] for r in ORDRE],
        "valeurs": [VALEUR_VENTE[r] for r in ORDRE],
        "requis_fantome": [REQUIS_FANTOME[r] for r in ORDRE],
        "couts_niveau": [COUT_NIVEAU[r] for r in ORDRE],
        "niveau_max": NIVEAU_MAX,
        "bonus": BONUS_FINITION,
        "chance_brillante": CHANCE_BRILLANTE,
        "chance_arc": CHANCE_ARC_EN_CIEL,
        "garantie_derniere": GARANTIE_DERNIERE,
        "taille_booster": TAILLE_BOOSTER,
        "pitie_apres": PITIE_APRES,
        "pitie_rarete": PITIE_RARETE,
        "intervalle_ms": INTERVALLE_SECONDES * 1000,
        "stock_max": STOCK_MAX,
        "depart": BOOSTERS_DEPART,
        "boutique": BOUTIQUE,
        "roue": ROUE,
        "multi_duree_ms": MULTI_DUREE_SECONDES * 1000,
        "admin": ADMIN_PSEUDO,
    }, ensure_ascii=False)


def nouvel_etat_web(maintenant):
    return json.dumps(etat_initial(maintenant), ensure_ascii=False)


def synchroniser_web(etat_json, maintenant):
    return json.dumps(synchroniser(json.loads(etat_json), maintenant), ensure_ascii=False)


def ouvrir_booster_web(cartes_json, etat_json, maintenant, mode):
    cartes = json.loads(cartes_json)
    etat = json.loads(etat_json)
    try:
        tirage, pitie = ouvrir_booster(cartes, etat, maintenant, mode)
    except ValueError as e:
        return json.dumps({"erreur": str(e), "etat": etat}, ensure_ascii=False)
    return json.dumps({"cartes": tirage, "pitie": pitie, "etat": etat}, ensure_ascii=False)


def ouvrir_masse_web(cartes_json, etat_json, maintenant, mode, nombre):
    """Admin : ouvre `nombre` boosters d'un coup et renvoie un résumé (pas le détail de chaque tirage)."""
    cartes = json.loads(cartes_json)
    etat = json.loads(etat_json)
    nombre = max(1, min(int(nombre), 5000))
    par_rarete = {r: 0 for r in ORDRE}
    finitions = {"brillante": 0, "arc-en-ciel": 0}
    nouvelles = pieces = doublons = 0
    meilleures = {}  # (id, finition) -> nombre d'exemplaires, pour les raretés ultra rare et mieux
    seuil = ORDRE.index("ultra rare")
    for _ in range(nombre):
        tirage, _pitie = ouvrir_booster(cartes, etat, maintenant, mode)
        for c in tirage:
            par_rarete[c["rarete"]] += 1
            if c["finition"] in finitions:
                finitions[c["finition"]] += 1
            nouvelles += 1 if c["nouvelle"] else 0
            if c["doublon"]:
                doublons += 1
                pieces += c["valeur"]
            if ORDRE.index(c["rarete"]) >= seuil or c["finition"] != "normale":
                cle = (c["id"], c["finition"])
                meilleures[cle] = meilleures.get(cle, 0) + 1
    liste = [{"id": i, "finition": f, "nb": n} for (i, f), n in meilleures.items()]
    return json.dumps({
        "nombre": nombre, "cartes": nombre * TAILLE_BOOSTER, "par_rarete": [par_rarete[r] for r in ORDRE],
        "finitions": finitions, "nouvelles": nouvelles, "doublons": doublons, "pieces": pieces, "meilleures": liste, "etat": etat,
    }, ensure_ascii=False)


def vendre_web(etat_json, cartes_json, carte_id, nombre):
    """nombre <= 0 : tous les doublons de la carte."""
    etat, cartes = json.loads(etat_json), json.loads(cartes_json)
    try:
        gain = vendre(etat, cartes, int(carte_id), None if int(nombre) <= 0 else int(nombre))
    except ValueError as e:
        return json.dumps({"erreur": str(e), "etat": etat}, ensure_ascii=False)
    return json.dumps({"gain": gain, "etat": etat}, ensure_ascii=False)


def vendre_tous_web(etat_json, cartes_json):
    etat, cartes = json.loads(etat_json), json.loads(cartes_json)
    gain, vendus = vendre_tous(etat, cartes)
    return json.dumps({"gain": gain, "vendus": vendus, "etat": etat}, ensure_ascii=False)


def ameliorer_web(etat_json, cartes_json, carte_id):
    etat, cartes = json.loads(etat_json), json.loads(cartes_json)
    try:
        niveau = ameliorer(etat, cartes, int(carte_id))
    except ValueError as e:
        return json.dumps({"erreur": str(e), "etat": etat}, ensure_ascii=False)
    return json.dumps({"niveau": niveau, "etat": etat}, ensure_ascii=False)


def acheter_web(etat_json, offre_id, maintenant):
    etat = json.loads(etat_json)
    erreur = acheter(etat, offre_id, maintenant)
    return json.dumps({"erreur": erreur, "etat": etat}, ensure_ascii=False)


def attente_web(etat_json, maintenant):
    return json.dumps(attente(json.loads(etat_json), maintenant))


def tourner_roue_web(etat_json, jour, maintenant):
    etat = json.loads(etat_json)
    erreur, gain = tourner_roue(etat, jour, maintenant)
    return json.dumps({"erreur": erreur, "etat": etat, "gain": gain}, ensure_ascii=False)


def utiliser_code_web(etat_json, code, recompense_json, maintenant):
    etat = json.loads(etat_json)
    erreur, gain = utiliser_code(etat, code, json.loads(recompense_json), maintenant)
    return json.dumps({"erreur": erreur, "etat": etat, "gain": gain}, ensure_ascii=False)


def calculer_profil(etat, cartes):
    """Les chiffres du profil d'un joueur (ceux du classement). Le score est recalculé à partir de la collection."""
    rarete_de = {c["id"]: c["rarete"] for c in cartes}
    score, possedees, brillantes, arcs = 0.0, 0, 0, 0
    par_rarete = {r: 0 for r in ORDRE}
    for cle, n in etat.get("collection", {}).items():
        r = rarete_de.get(int(cle))
        if r is None or n <= 0:
            continue
        f = etat.get("finitions", {}).get(cle, {})
        b, a = f.get("brillante", 0), f.get("arc-en-ciel", 0)
        score += POINTS[r] * (max(n - b - a, 0) + b * BONUS_FINITION["brillante"] + a * BONUS_FINITION["arc-en-ciel"])
        score += POINTS[r] * BONUS_POINTS_NIVEAU[min(etat.get("niveaux", {}).get(cle, 1), NIVEAU_MAX) - 1]
        possedees += 1
        par_rarete[r] += 1
        brillantes += 1 if b > 0 else 0
        arcs += 1 if a > 0 else 0

    # "chance" : points tirés par booster, comparés à ce qu'un booster rapporte en moyenne (100 % = dans la moyenne)
    attendu = etat.get("stat_attendu", 0.0)
    chance = round(100 * etat.get("stat_points", 0) / attendu) if etat.get("stat_boosters", 0) >= 5 and attendu else None

    # la vitrine ne garde que des cartes (et finitions) que le joueur possède vraiment
    par_id = {c["id"]: c for c in cartes}
    vitrine = []
    for v in etat.get("vitrine", [])[:3]:
        cle = str(v.get("id"))
        f = etat.get("finitions", {}).get(cle, {})
        fin = v.get("finition", "normale")
        carte = par_id.get(v.get("id"))
        if carte and etat.get("collection", {}).get(cle, 0) > 0 and fantome_revelee(etat, carte) and (fin == "normale" or f.get(fin, 0) > 0):
            vitrine.append({"id": v["id"], "finition": fin, "niveau": niveau_carte(etat, v["id"])})
    fantomes = [c for c in cartes if c.get("fantome")]
    niveaux = [niveau_carte(etat, c["id"]) for c in cartes if etat.get("collection", {}).get(str(c["id"]), 0) > 0]
    return {
        "fantomes": sum(1 for c in fantomes if fantome_revelee(etat, c) and etat.get("collection", {}).get(str(c["id"]), 0) > 0),
        "fantomes_total": len(fantomes),
        "niveau_max": sum(1 for n in niveaux if n >= NIVEAU_MAX), "niveaux": sum(n - 1 for n in niveaux),
        "score": int(round(score)), "possedees": possedees, "total": len(cartes),
        "boosters": etat.get("boosters_ouverts", 0), "brillantes": brillantes, "arcs": arcs,
        "par_rarete": [par_rarete[r] for r in ORDRE], "chance": chance, "vitrine": vitrine,
    }


def profil_web(etat_json, cartes_json):
    return json.dumps(calculer_profil(json.loads(etat_json), json.loads(cartes_json)), ensure_ascii=False)
