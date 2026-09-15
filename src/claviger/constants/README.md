# Constants

Ce dossier contient les constantes partagées dont la valeur appartient réellement au code.

Une constante est appropriée lorsqu'une valeur :

- est stable ;
- n'est pas spécifique à une guild ;
- ne doit pas être configurée dynamiquement ;
- ne représente pas un état persistant.

Les valeurs liées à la configuration d'un serveur, à une policy ou à la base ne doivent pas être déplacées ici uniquement pour éviter de les passer explicitement.
