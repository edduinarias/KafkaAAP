# Demo en vivo · Kafka DR

Página local que muestra, en vivo, el estado de la pareja de Kafka y lo que hace la automatización
de AAP sobre ella. Está pensada para presentar la solución a BPD: un funcional entiende qué pasa
(quién atiende, qué se copia hacia dónde, si los dos sitios tienen lo mismo) y un técnico ve el
detalle (brokers, réplicas, proxies, cada acción con su rol).

**No va a git.** Vive en `_contexto/`, que está ignorado.

## Uso

```bash
cd _contexto/demo
make up          # levanta las dos pantallas y espera a que respondan
make status      # cada fuente, con su última lectura
make logs
make down
```

Son dos pantallas del mismo proceso, que ven el mismo estado:

| Pantalla | Dirección | Para qué |
| --- | --- | --- |
| **Vista en vivo** | http://127.0.0.1:8765 | La que se proyecta. Solo mira: no acepta ninguna acción. |
| **Consola de la demo** | http://127.0.0.1:8766 | La del presentador: el guion paso a paso (qué decir, qué hacer, qué vas a ver), los escenarios, Temenos y los casos de uso. |

La consola se organiza por caso de uso, uno por capítulo del procedimiento operativo de BPD
(`_contexto/1-fuente/BPD-Procedimiento-Operativo.md`): Failover §2.1, Failback §2.2 y §2.3, Rotación
§3 y Conmutación planificada §1.2. Para cada caso anticipa qué va a decidir la automatización con el
ambiente como está. Los casos se definen en `casos_demo.yml`, el recorrido sugerido en `guion.yml` y
los escenarios en `escenarios.yml`; cada texto cita la sección del procedimiento de la que sale.

Cada caso trae además su **procedimiento**: la tabla de pasos del documento, paso por paso, con quién
lo hace (tú, la automatización, no se ejecuta, o fuera de esta pareja por ser de Integrations), cómo
se hace en la demo y por qué, citado del documento. El título y la explicación de cada paso se leen
del documento al vuelo, no se copian; `casos_demo.yml` solo anota quién y cómo.

Con el guion en marcha («Recorrido sugerido» → «Iniciar el guion»), el caso de la izquierda sigue al
paso actual: Failover en los pasos 1 a 5, Failback desde el 6, con la etapa y el procedimiento de
cada paso. Si se elige otro caso a mano, se respeta hasta el paso siguiente.

### Antes de presentar

1. **Los tokens de admin duran 24 h.** Si vencieron o vencen durante la demo, renovarlos: por cada
   sitio, `oc login <api> -u <admin>` y `oc whoami -t > ~/.config/aap/adm-<sitio>`. Después,
   `../herramientas/renovar-tokens.py` los valida, los carga juntos en la credencial de AAP y corre
   el Discover para confirmarlo. `--solo-validar` muestra cuándo vencen, sin tocar nada.
2. `make limpio`: la línea de tiempo arranca vacía; el caso elegido y el guion se conservan.
3. En la vista en vivo: «Operación normal», el mismo contenido en los dos sitios y Temenos detenido.

`make up PUERTO=8800 PUERTO_CONSOLA=8801` cambia los puertos. `make up HOST=0.0.0.0` la deja visible desde otras
máquinas: cualquiera que la abra puede publicar transacciones de prueba en el laboratorio.

Requisitos: `python3` con PyYAML (los del sistema alcanzan) y los mismos accesos que la CLI:

| Qué | De dónde |
|---|---|
| Token de cada sitio | `~/.config/aap/adm-co` y `~/.config/aap/adm-ca` |
| Token y URL de AAP | `~/.config/aap/env` (`AAP_API`, `AAP_URL`, `AAP_TOKEN_FILE`) |
| Inventario y contrato | `playbooks/group_vars/all/` y `transitions.yml` del proyecto |

Los tokens se releen en cada consulta: renovados en disco, la página los toma sin reiniciar. Su
valor nunca sale del servidor; la página muestra identidad y vencimiento.

## Qué muestra

| Panel | Qué es | De dónde sale |
|---|---|---|
| Situación | La frase que resume el momento y qué sitio atiende | Todo lo de abajo |
| El ambiente | Cada sitio con su camino Temenos → Proxy → Kafka → Aplicaciones, y las dos réplicas | API de Kubernetes de cada sitio |
| Línea de tiempo | Cada cambio del ambiente y de la operación, en palabras | Comparación entre lecturas |
| Operación de AAP | La última operación: fases, plan, cómo debe quedar (en vivo), controles | API de AAP: nodos, artefacto `wf_kafka_plan`, eventos |
| Datos en vivo | Mensajes, consumidos y pendientes por sitio; si el contenido es igual | Exporter de Kafka, por el proxy de la API |
| Temenos | Publica transacciones de prueba por la micro-app productora del sitio | `kafka-producer-app` (`POST /api/batch`) |
| Casos de uso | Matriz pareja × caso: certificado, en construcción, próximo | `transitions.yml` + `catalogo.yml` |

La página no lanza ni aprueba operaciones: eso se hace en AAP, y la página lo muestra.

Los offsets salen del exporter de Kafka que el ambiente ya tiene. La página no ejecuta nada
dentro de los brokers (hallazgo N19).

## Cómo se extiende

- **Una operación nueva** (la Rotación, por ejemplo): se declara en el contrato como siempre. Si
  su `operacion` está en `catalogo.yml` con su `caso`, aparece en la matriz y en la lista de
  operaciones lanzables; si no, aparece igual con su nombre técnico. Sus acciones se describen solas si usan
  roles conocidos; un rol nuevo se agrega en `servidor/modelo.py` (`_accion`).
- **Integrations**: al sumarse a `parejas.yml`, `pareja: integrations` en `config.yml` la muestra.
  La topología se arma con el inventario de la pareja.
- **Un panel nuevo**: un módulo en `web/vistas/` con `montar()` y `actualizar(estado)`, sumado a
  `VISTAS` en `web/app.js` y con su contenedor en `index.html`.
- **Logos**: `web/assets/logo-cliente.svg|png` y `web/assets/logo-redhat.svg|png`. Si están, se
  usan; si no, queda el texto.

## Estructura

```
config.yml          puertos, rutas de tokens, intervalos
catalogo.yml        nombres funcionales y estado de cada caso de uso
Makefile
servidor/
  app.py            servidor HTTP, recolectores en segundo plano, SSE
  fuentes.py        configuración, tokens, HTTP
  sitios.py         lectura de cada sitio y del exporter
  aap.py            la operación, leída de AAP
  credenciales.py   identidad y vencimiento de los tokens
  temenos.py        el simulador de transacciones
  modelo.py         todo lo anterior en lenguaje funcional, y la línea de tiempo
  procedimiento.py  los pasos de cada sección, leídos del procedimiento operativo
web/
  index.html  estilos.css  app.js
  vistas/           un módulo por panel
  assets/fuentes/   Red Hat Display, Text y Mono (OFL), locales
```

Colores: cada sitio tiene uno propio en toda la página (CO azul, CA naranja), validados para
daltonismo en claro y en oscuro. Los colores de estado van siempre con icono y texto. El rojo de
Red Hat aparece solo en la firma de autoría.
