"""\
GLO-2000 Travail pratique 4 - Client 2026
Noms et numéros étudiants:
-Maxime Lamothe 537 068 779
-Alexandre Therrien 537 294 449
"""

import argparse
import getpass
import json
import socket
import sys

import glosocket
import gloutils


class Client:
    """Client pour le serveur mail @glo2000.ca 2026."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """
        self._username = ""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((destination, gloutils.APP_PORT))
        except OSError:
            print("Connection impossible")
            self._socket.close()
            sys.exit(1)

    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        usernameInput = input("Entrez un nom d'utilisateur: ")
        motDePasseInput = getpass.getpass("Entrez un mot de passe: ")
        payload = gloutils.AuthPayload(username= usernameInput, password= motDePasseInput)
        message = gloutils.GloMessage(header= gloutils.Headers.AUTH_REGISTER,payload= payload)
        glosocket.send_mesg(self._socket, json.dumps(message))

        dataReceived = glosocket.recv_mesg(self._socket)
        dataDict = json.loads(dataReceived)

        if dataDict["header"] == gloutils.Headers.ERROR:
            print(dataDict["payload"]["error_message"])

        elif dataDict["header"] == gloutils.Headers.OK:
            self._username = usernameInput





    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """

        usernameInput = input("Entrez un nom d'utilisateur: ")
        motDePasseInput = getpass.getpass("Entrez un mot de passe: ")
        payload = gloutils.AuthPayload(username=usernameInput, password=motDePasseInput)
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_LOGIN, payload=payload)
        glosocket.send_mesg(self._socket, json.dumps(message))

        dataReceived = glosocket.recv_mesg(self._socket)
        dataDict = json.loads(dataReceived)

        if dataDict["header"] == gloutils.Headers.ERROR:
            print(dataDict["payload"]["error_message"])

        elif dataDict["header"] == gloutils.Headers.OK:
            self._username = usernameInput




    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.BYE)
        glosocket.send_mesg(self._socket, json.dumps(message))
        self._socket.close()

    def _read_email(self) -> None:
        """
        Demande au serveur la liste de ses courriels avec l'entête
        `INBOX_READING_REQUEST`.

        Affiche la liste des courriels puis transmet le choix de l'utilisateur
        avec l'entête `INBOX_READING_CHOICE`.

        Affiche le courriel à l'aide du gabarit `EMAIL_DISPLAY`.

        S'il n'y a pas de courriel à lire, l'utilisateur est averti avant de
        retourner au menu principal.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.INBOX_READING_REQUEST)
        glosocket.send_mesg(self._socket, json.dumps(message))


        dataReceived = glosocket.recv_mesg(self._socket)
        dataDict = json.loads(dataReceived)
        emailList = dataDict["payload"]["email_list"]
        for emailStr in emailList:
            print(emailStr)

        if len(emailList) > 0:
            choixEmail = -1
            while(choixEmail == -1):
                try:
                    intInput= int(input(f"Entrez votre choix [1-{len(emailList)}]:"))
                    if intInput >= 1 and intInput <= len(emailList): #si valide
                        choixEmail = intInput
                    else:
                        raise ValueError
                except ValueError:
                    print(f"Choix invalide, Entrez un numbre entier entre 1 et {len(emailList)}.")

            payload = gloutils.EmailChoicePayload(choice=choixEmail)
            message = gloutils.GloMessage(header= gloutils.Headers.INBOX_READING_CHOICE, payload=payload)
            glosocket.send_mesg(self._socket, json.dumps(message))

            dataReceived = glosocket.recv_mesg(self._socket)
            dataDict = json.loads(dataReceived)

            emailToPrint = gloutils.EMAIL_DISPLAY.format(
                sender = dataDict["payload"]["sender"],
                to = dataDict["payload"]["destination"],
                subject = dataDict["payload"]["subject"],
                date = dataDict["payload"]["date"] ,
                body = dataDict["payload"]["content"]
            )
            print(emailToPrint) 
        else:
            print("Vous n'avez aucun courriel")
        






    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """
        sender = f"{self._username}@{gloutils.SERVER_DOMAIN}"
        destination = input("Entrez l'adresse du destinataire: ")
        subject = input("Entrez le sujet: ")
        date = gloutils.get_current_utc_time()

        print("Entrez le contenu du courriel, terminez la saisie avec un '.' seul sur une ligne: ")
        contentDone = False
        contentLines = []
        while not contentDone:
            line = input()
            if line == ".":
                contentDone = True
            else:
                contentLines.append(line)
        content = "\n".join(contentLines)

        payload = gloutils.EmailContentPayload(sender=sender, destination=destination, subject=subject, date=date, content=content)
        message = gloutils.GloMessage(header= gloutils.Headers.EMAIL_SENDING, payload=payload)
        glosocket.send_mesg(self._socket, json.dumps(message))


        dataReceived = glosocket.recv_mesg(self._socket)
        dataDict = json.loads(dataReceived)

        if dataDict["header"] == gloutils.Headers.ERROR:
            print(dataDict["payload"]["error_message"])





    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """

        message = gloutils.GloMessage(header=gloutils.Headers.STATS_REQUEST)
        glosocket.send_mesg(self._socket, json.dumps(message))

        dataReceived = glosocket.recv_mesg(self._socket)
        dataDict = json.loads(dataReceived)

        StatsToPrint = gloutils.STATS_DISPLAY.format(
            count = dataDict["payload"]["count"],
            size = dataDict["payload"]["size"]
        )
        print(StatsToPrint)



    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_LOGOUT)
        glosocket.send_mesg(self._socket, json.dumps(message))
        self._username = ""


    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:
            if not self._username:
                # Menu connection
                print(gloutils.CLIENT_AUTH_CHOICE)
                choiceInput = input("Entrez votre choix [1-3]: ")
                match choiceInput:
                    case "1": # Créer un compte
                        self._register()
                    case "2": # Se connecter
                        self._login()
                    case "3":  # Quitter
                        self._quit()
                        should_quit = True
                    case _: # entrée invalide
                        print(f"Choix invalide, Entrez un numbre entier entre 1 et 3")
            else:
                # Main menu
                print(gloutils.CLIENT_USE_CHOICES)
                choiceInput = input("Entrez votre choix [1-4]: ")
                match choiceInput:
                    case "1": # Consultation de courriels
                        self._read_email()
                    case "2": # Envoi de courriels
                        self._send_email()
                    case "3": # Statistiques
                        self._check_stats()
                    case "4": # Se déconnecter
                        self._logout()
                    case _: # entrée invalide
                        print(f"Choix invalide, Entrez un numbre entier entre 1 et 4")



# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT
# NE PAS ÉDITER PASSÉ CE POINT


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--destination",
        action="store",
        dest="dest",
        required=True,
        help="Adresse IP/URL du serveur.",
    )
    args = parser.parse_args(sys.argv[1:])
    client = Client(args.dest)
    client.run()
    return 0


if __name__ == "__main__":
    sys.exit(_main())
