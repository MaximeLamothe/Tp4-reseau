"""\
GLO-2000 Travail pratique 4 - Serveur 2026
Noms et numéros étudiants:
-Maxime Lamothe 537 068 779
-Alexandre Therrien 537 294 449
"""

import hashlib
import hmac
import json
import os
import select
import socket
import sys

import glosocket
import gloutils


class Server:
    """Serveur mail @glo2000.ca 2026."""

    def __init__(self) -> None:
        """
        Prépare le socket du serveur `_server_socket`
        et le met en mode écoute.

        Prépare les attributs suivants:
        - `_client_socs` une liste des sockets clients.
        - `_logged_users` un dictionnaire associant chaque
            socket client à un nom d'utilisateur.

        S'assure que les dossiers de données du serveur existent.
        """
        self._client_socs: list[socket.socket] = []
        self._logged_users: dict[socket.socket, str] = {}
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(("0.0.0.0", gloutils.APP_PORT))
            self._server_socket.listen()

        except OSError:
            print("Impossible de démarrer le serveur")
            self._server_socket.close()
            sys.exit(1)

        os.makedirs(os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR), exist_ok=True)


    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            client_soc.close()
        self._server_socket.close()

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        client_soc, _ = self._server_socket.accept()
        self._client_socs.append(client_soc)

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        self._logged_users.pop(client_soc, None)
        if client_soc in self._client_socs:
            self._client_socs.remove(client_soc)
        client_soc.close()

    def _create_account(
        self, client_soc: socket.socket, payload: gloutils.AuthPayload
    ) -> gloutils.GloMessage:
        """
        Crée un compte à partir des données du payload.

        Si les identifiants sont valides, créee le dossier de l'utilisateur,
        associe le socket au nouvel l'utilisateur et retourne un succès,
        sinon retourne un message d'erreur.
        """
        username = payload["username"]
        motDePasse = payload["password"]
        dossierUser = os.path.join(gloutils.SERVER_DATA_DIR, username.lower())
        erreurs = []

        usernameValide = (len(username) > 0 and username.isascii() and all(lettre.isalnum() or lettre in "_.-" for lettre in username))

        if not usernameValide:erreurs.append("Le nom d'utilisateur est invalide.")
        elif (username.lower() == gloutils.SERVER_LOST_DIR.lower() or os.path.exists(dossierUser)):erreurs.append("Le nom d'utilisateur est déjà pris.")
        if not (len(motDePasse) >= 10
                and any(c in "0123456789" for c in motDePasse) and any(c.islower() for c in motDePasse) and any(c.isupper() for c in motDePasse)):
            erreurs.append("Le mot de passe n'est pas assez sûr.")

        if len(erreurs) > 0:
            messageErreur = "\n".join(f"- {erreur}" for erreur in erreurs)
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR,
                payload=gloutils.ErrorPayload(error_message=messageErreur)
            )

        motDePasseHache = hashlib.sha3_512(motDePasse.encode("utf-8")).hexdigest()
        try:
            os.mkdir(dossierUser)
            with open(os.path.join(dossierUser, gloutils.PASSWORD_FILENAME),
                      "w", encoding="utf-8") as fichier:fichier.write(motDePasseHache)
        except OSError:
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR,
                payload=gloutils.ErrorPayload(error_message="Impossible de créer le compte.")
            )

        self._logged_users[client_soc] = username
        return gloutils.GloMessage(header=gloutils.Headers.OK)

    def _login(
        self, client_soc: socket.socket, payload: gloutils.AuthPayload
    ) -> gloutils.GloMessage:
        """
        Vérifie que les données fournies correspondent à un compte existant.

        Si les identifiants sont valides, associe le socket à l'utilisateur et
        retourne un succès, sinon retourne un message d'erreur.
        """
        username = payload["username"]
        motDePasse = payload["password"]
        erreur = gloutils.GloMessage(
            header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Nom d'utilisateur ou mot de passe invalide."),
        )

        usernameValide = (len(username) > 0 and username.isascii() and all(lettre.isalnum() or lettre in "_.-" for lettre in username))

        if (not usernameValide or username.lower() == gloutils.SERVER_LOST_DIR.lower()):
            return erreur

        cheminPass = os.path.join(gloutils.SERVER_DATA_DIR, username.lower(), gloutils.PASSWORD_FILENAME)
        try:
            with open(cheminPass, "r", encoding="utf-8") as fichier:
                motDePasseStocke = fichier.read()
        except OSError:
            return erreur

        motDePasseCache = hashlib.sha3_512(motDePasse.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(motDePasseCache, motDePasseStocke):
            return erreur

        self._logged_users[client_soc] = username
        return gloutils.GloMessage(header=gloutils.Headers.OK)

    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        self._logged_users.pop(client_soc, None)

    def _get_email_list(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        dossierUser = os.path.join(gloutils.SERVER_DATA_DIR, self._logged_users[client_soc].lower())
        courriels = []

        for nomFichier in os.listdir(dossierUser):
            if nomFichier == gloutils.PASSWORD_FILENAME:
                continue

            chemin = os.path.join(dossierUser, nomFichier)
            try:
                with open(chemin, "r", encoding="utf-8") as fichier: contenu = json.load(fichier)
                modifie = os.path.getmtime(chemin)
            except (OSError, json.JSONDecodeError) as err:
                continue

            if not isinstance(contenu, dict) or not all(cle in contenu for cle in("sender", "destination", "subject", "date", "content")):
                continue
            courriels.append((modifie, nomFichier, contenu))

        courriels.sort(key=lambda item: (item[0], item[1]), reverse=True)
        listeEmail = []
        for numero, item in enumerate(courriels, start=1):
            listeEmail.append(gloutils.SUBJECT_DISPLAY.format(
                number=numero,
                sender=item[2]["sender"],
                subject=item[2]["subject"],
                date=item[2]["date"],
            ))
        return gloutils.GloMessage(header=gloutils.Headers.OK,payload=gloutils.EmailListPayload(email_list=listeEmail))

    def _get_email(
        self, client_soc: socket.socket, payload: gloutils.EmailChoicePayload
    ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        dossierUser = os.path.join(gloutils.SERVER_DATA_DIR, self._logged_users[client_soc].lower())

        courriels = []

        for nomFichier in os.listdir(dossierUser):
            if nomFichier == gloutils.PASSWORD_FILENAME:
                continue

            chemin = os.path.join(dossierUser, nomFichier)
            try:
                with open(chemin, "r", encoding="utf-8") as fichier:
                    contenu = json.load(fichier)
                modifie = os.path.getmtime(chemin)
            except (OSError, json.JSONDecodeError) as err:
                continue

            if not isinstance(contenu, dict) or not all(
                    cle in contenu for cle in ("sender", "destination", "subject", "date", "content")):
                continue
            courriels.append((modifie, nomFichier, contenu))

        courriels.sort(key=lambda item: (item[0], item[1]), reverse=True)

        choix = payload["choice"]
        if not isinstance(choix, int) or not 1 <= choix <= len(courriels):
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Ce courriel n'existe pas.")
            )

        return gloutils.GloMessage(header=gloutils.Headers.OK, payload=courriels[choix - 1][2])

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """

        dossierUser = os.path.join(gloutils.SERVER_DATA_DIR, self._logged_users[client_soc].lower())
        nbCourriels = 0
        tailleTot = 0
        for nomFichier in os.listdir(dossierUser):
            chemin = os.path.join(dossierUser, nomFichier)
            if not os.path.isfile(chemin):
                continue
            tailleTot += os.path.getsize(chemin)
            if nomFichier != gloutils.PASSWORD_FILENAME:
                nbCourriels += 1

        return gloutils.GloMessage(
            header=gloutils.Headers.OK,payload=gloutils.StatsPayload(count=nbCourriels, size=tailleTot)
            )

    def _send_email(self, payload: gloutils.EmailContentPayload) -> gloutils.GloMessage:
        """
        Détermine si l'envoi est interne ou externe et:
        - Si l'envoi est interne, écris le message tel quel dans le dossier
        du destinataire.
        - Si le destinataire n'existe pas, place le message dans le dossier
        SERVER_LOST_DIR et considère l'envoi comme un échec.
        - Si le destinataire est externe, considère l'envoi comme un échec.

        Retourne un messange indiquant le succès ou l'échec de l'opération.
        """
        nom, at, domaine = payload["destination"].strip().rpartition("@")
        if (at == "" or nom == "" or domaine.lower() != gloutils.SERVER_DOMAIN):
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Le destinataire est externe au serveur."),
            )

        destinataire = nom.lower()
        dossierDestinataire = os.path.join(gloutils.SERVER_DATA_DIR, destinataire)

        nomValide = (destinataire.isascii() and all(lettre.isalnum() or lettre in "_.-" for lettre in destinataire))
        existe = (nomValide and destinataire != gloutils.SERVER_LOST_DIR.lower() and os.path.isdir(dossierDestinataire))
        if existe:
            dossierCible = dossierDestinataire
        else:
            dossierCible = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)

        numero = len(os.listdir(dossierCible))
        cheminCourriel = os.path.join(dossierCible, f"{numero:06d}.json")

        while os.path.exists(cheminCourriel):
            numero += 1
            cheminCourriel = os.path.join(dossierCible, f"{numero:06d}.json")

        try:
            with open(cheminCourriel, "w", encoding="utf-8") as fichier:
                json.dump(payload, fichier)

        except OSError:
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Impossible d'enregistrer le courriel.")
            )

        if not existe:
            return gloutils.GloMessage(
                header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Le destinataire n'existe pas.")
            )

        return gloutils.GloMessage(header=gloutils.Headers.OK)

    def run(self):
        """Point d'entrée du serveur."""
        waiters = []
        while True:
            # Select readable sockets
            waiters, _, _ = select.select([self._server_socket]+self._client_socs, [], [])

            for waiter in waiters:
                # Handle sockets
                if waiter is self._server_socket:
                    self._accept_client()
                    continue
                try:
                    message = json.loads(glosocket.recv_mesg(waiter))
                except (glosocket.GloSocketError, json.JSONDecodeError):
                    self._remove_client(waiter)
                    continue

                reponse = None
                header = message["header"]
                if header == gloutils.Headers.BYE:
                    self._remove_client(waiter)
                    continue
                elif header == gloutils.Headers.AUTH_REGISTER:
                    reponse = self._create_account(waiter, message["payload"])
                elif header == gloutils.Headers.AUTH_LOGIN:
                    reponse = self._login(waiter, message["payload"])
                elif header == gloutils.Headers.AUTH_LOGOUT:
                    self._logout(waiter)
                    continue
                elif waiter not in self._logged_users:
                    reponse = gloutils.GloMessage(
                        header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Vous n'êtes pas authentifié.")
                    )
                elif header == gloutils.Headers.INBOX_READING_REQUEST:
                    reponse = self._get_email_list(waiter)
                elif header == gloutils.Headers.INBOX_READING_CHOICE:
                    reponse = self._get_email(waiter, message["payload"])
                elif header == gloutils.Headers.EMAIL_SENDING:
                    reponse = self._send_email(message["payload"])
                elif header == gloutils.Headers.STATS_REQUEST:
                    reponse = self._get_stats(waiter)
                else:
                    reponse = gloutils.GloMessage(
                        header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Requête invalide.")
                    )

                try:
                    glosocket.send_mesg(waiter, json.dumps(reponse))
                except glosocket.GloSocketError:
                    self._remove_client(waiter)


# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT


def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(_main())