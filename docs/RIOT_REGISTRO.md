# Riot: registro y reglas que afectan a LOL-E (consultado el 27/11/2026)

## Lo que dicen los textos oficiales

- **Hay que registrar el producto.** «If your product serves players, you must register it with us regardless of whether or not your product
  uses official documented APIs» ([docs/lol](https://developer.riotgames.com/docs/lol)). Cada cambio o función nueva se actualiza en su ficha
  ([políticas generales](https://developer.riotgames.com/policies/general), 29/05/2025).
- La API del cliente (LCU) **no tiene soporte oficial**: puede cambiar sin aviso. Piden indicar qué rutas se usan y para qué
  ([aviso de 2019](https://riotgames.com/en/DevRel/new-league-client-api-policy)).
- **Ningún texto consultado permite ni prohíbe** escribir runas u objetos, ni el envío automático que activa el jugador.
- Reglas que pueden aplicarse: «Apps that dictate player decisions» figura entre los usos no aprobados, y «Products should not remove game
  decisions, but may highlight decisions that are important and give multiple choices».

Lectura propia (no es de Riot): el envío con botón deja la decisión al jugador. El automático es más discutible, aunque va apagado de serie,
manda la página que se está viendo y se puede elegir otra; conviene preguntarlo en el registro. La parte de la LCU de la página se leyó a través
de un resumen: antes de enviar el registro, comprobarla en el navegador.

## Borrador para la ficha del producto (lo envía el usuario; no se ha enviado nada)

> **LOL-E** is a free Windows desktop companion app (Spanish UI) for League of Legends. It helps the player decide during champion select and
> review their own games afterwards. It shows information and options; the player makes every decision. It never accepts queues, picks or bans,
> and it does not read game memory or inject anything.
>
> **League Client API, read:** gameflow phase and session, champion select session, lobby members, current summoner, ranked stats, match history
> and timelines, champion mastery and owned champions, challenges, honor, ready check (read only), and the profile of the other
> players in the current champion select or game (rank, recent matches, mastery), as far as the client provides it. Builds and meta statistics come
> from Lolalytics and op.gg.
>
> **League Client API, write (only on the player's request):** one rune page named "LOL-E · champion" (`/lol-perks/v1/pages`,
> `/lol-perks/v1/currentpage`; other pages are never deleted) and item sets named "LOL-E · …" (`/lol-item-sets/v1/item-sets`). Each has a button;
> each also has an optional switch, off by default, that sends them when the player locks a champion.
>
> **Live Client Data API:** scoreboard, items and objective events of the player's own game.
>
> **Question:** is the optional automatic sending of rune pages and item sets acceptable, or should it be button only?

Lista de rutas contrastada con el código el 27/11/2026; repasarla si se añaden funciones.
