# Notas de la 1.32.0 (publicada; ya pasadas a `novedades.py` y `NOTAS_DE_VERSION.txt`)

Al publicar: pasar este texto a `novedades.py` (arriba de `NOTES`) y a `docs/NOTAS_DE_VERSION.txt`, subir `APP_VERSION` y borrar este archivo.

## Para el usuario («Novedades»)

**Título:** Lo que ya sabes de tus partidas, a la vista

| Tipo | Texto |
|---|---|
| nuevo | Al acabar una partida de la Grieta, «Análisis» empieza con un resumen: resultado y puntos de liga, tu objetivo y una sola cosa a mejorar. «Ver el análisis completo» abre lo demás. |
| nuevo | Bajo el rival de línea ves tu historial contra ese campeón: partidas, victorias y cómo ibas en el minuto 10. |
| nuevo | Si juegas en dúo o en grupo, en la selección aparece cómo os va juntos, cómo te va sin esa persona y la pareja de campeones que mejor os ha salido. |
| nuevo | LOL-E analiza en segundo plano tus últimas partidas de la Grieta, solo fuera de cola y de partida: el objetivo ya no depende de haber jugado con la app abierta. |
| mejora | La gráfica de rango ya no estima nada: solo enseña tus PL reales y las fotos de op.gg. Si acabas de instalar LOL-E, ves además tus victorias y derrotas reales de las clasificatorias que guarda el cliente. |
| mejora | Bajo «Enviar runas al cliente» se avisa si lo que ves ya no es lo que enviaste. |
| mejora | Repasados los textos de toda la aplicación y muchos detalles visuales, sobre todo con la ventana estrecha. |
| arreglo | Si abres LOL-E con otra partida ya empezada, ya no enseña la build de la anterior. |
| arreglo | El envío automático de objetos ya no deja en el cliente una build antigua. |
| arreglo | Un corte del juego al terminar ya no pierde el análisis, y al cerrarlo la franja deja de decir que estás en partida. |
| arreglo | Una selección abandonada ya no aparece como «Última partida», y cada selección empieza por la mejor recomendación. |

## Para el desarrollador (`NOTAS_DE_VERSION.txt`)

- Nuevos: `backfill.py`, `rivals.py`, `duo.py`, resumen en `ui_analysis` (tres columnas desde 760, franja y frases por debajo).
- Tres revisiones de especialistas (mejoras acumuladas, visual a 560 y 1340, estados entre partidas) y una de textos.
- Sin ver en una partida real: todo lo anterior salvo el repaso en segundo plano (probado contra el cliente real en carpeta temporal).
- Límite conocido: `cache/analysis` es común a todas las cuentas.
