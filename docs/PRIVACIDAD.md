# Privacidad de LOL-E

LOL-E funciona en tu ordenador. Lee tu cliente de League of Legends y fuentes públicas (Data Dragon, Lolalytics, op.gg, las notas de parche de Riot) y guarda tu historial,
tus ajustes y sus cachés en tu propio perfil de Windows (`%LOCALAPPDATA%\LOL-E`). **No hay cuentas, ni anuncios, ni telemetría activa por defecto.**

## Cuenta anónima de instalaciones (opcional, apagada de fábrica)

Si el mantenedor ha configurado un servidor, LOL-E te preguntará **una sola vez** si quieres «contar tu instalación». Si dices que no (o cierras la ventana), no se envía nada.
Si dices que sí:

**Se envía**, como mucho una vez al día:
- un **número aleatorio** de esta instalación (se crea al aceptar; no sale de tu nombre, tu cuenta de LoL ni tu equipo);
- la **versión** de LOL-E.

**No se envía**: tu nombre, tu cuenta de LoL (ni su identificador), tus partidas, tu historial, tus ajustes, rutas, nombres de archivos ni nada de tu ordenador.

**Qué hace el servidor**: deduce de tu conexión una **zona aproximada** (país, región y unas coordenadas redondeadas a unos 50 km) y **descarta tu dirección IP** (no la guarda).
Guarda por instalación: el número aleatorio, la versión, la zona aproximada y los días en que avisó (últimos 120). Solo lo ve el mantenedor, con una clave, en un panel privado.

**Cómo apagarlo**: Ajustes › Privacidad › «Contar mi instalación». Al apagarlo, LOL-E borra tu número y pide al servidor que borre el registro de esa instalación.
Ver exactamente qué se envía: el botón «Ver exactamente qué se envía» (ventana de permiso y Ajustes).

El código es público: `stats.py` (lo que envía la app) y `servidor/worker.js` (lo que hace el servidor).
