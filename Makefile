# La pagina local de la demo de Kafka DR. Este directorio NO va a git.
#
#   make up        levanta la vista en vivo y la consola, y espera a que respondan
#   make down      la baja
#   make restart   down + up
#   make limpio    down + up con la linea de tiempo vacia: conserva el caso
#                  elegido y el guion, y respalda la memoria anterior en run/
#   make status    si esta arriba y como esta cada fuente
#   make logs      sigue el log
#   make check     revisa que este todo lo necesario, sin levantar nada
#
# Variables: HOST y PUERTO (por omision, las de config.yml). Con HOST=0.0.0.0
# la pagina queda visible desde otras maquinas: cualquiera que la abra puede
# publicar transacciones de prueba en el laboratorio.

SHELL  := /bin/bash
DEMO   := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PY     ?= python3
CONF    = $(PY) -c "import yaml,sys; c=yaml.safe_load(open('$(DEMO)/config.yml')); print(c['servidor'][sys.argv[1]])"
HOST   ?= $(shell $(CONF) host)
PUERTO ?= $(shell $(CONF) puerto)
PUERTO_CONSOLA ?= $(shell $(CONF) puerto_consola)
PID    := $(DEMO)/run/demo.pid
LOG    := $(DEMO)/logs/demo.log
URL     = http://$(if $(filter 0.0.0.0,$(HOST)),127.0.0.1,$(HOST)):$(PUERTO)
URL_CONSOLA = http://$(if $(filter 0.0.0.0,$(HOST)),127.0.0.1,$(HOST)):$(PUERTO_CONSOLA)

.PHONY: help up down restart limpio status logs check

help:
	@sed -n '3,11p' $(lastword $(MAKEFILE_LIST)) | sed 's/^# \{0,1\}//'

check:
	@ok=1; \
	command -v $(PY) >/dev/null || { echo "  ✗ falta $(PY)"; ok=0; }; \
	$(PY) -c "import yaml" 2>/dev/null && echo "  ✓ python y PyYAML" || { echo "  ✗ falta PyYAML (dnf install python3-pyyaml)"; ok=0; }; \
	[ -f "$(DEMO)/config.yml" ] && echo "  ✓ config.yml" || { echo "  ✗ falta config.yml"; ok=0; }; \
	for s in co ca; do \
	  f=$$($(PY) -c "import yaml,os; print(os.path.expanduser(yaml.safe_load(open('$(DEMO)/config.yml'))['tokens']['$$s']))"); \
	  [ -s "$$f" ] && echo "  ✓ token de $${s^^} ($$(basename $$f))" || { echo "  ✗ no hay token de $${s^^} en $$f"; ok=0; }; \
	done; \
	e=$$($(PY) -c "import yaml,os; print(os.path.expanduser(yaml.safe_load(open('$(DEMO)/config.yml'))['aap']['env']))"); \
	[ -f "$$e" ] && echo "  ✓ entorno de AAP ($$e)" || { echo "  ✗ falta el entorno de AAP: $$e"; ok=0; }; \
	[ -f "$(DEMO)/../../transitions.yml" ] && echo "  ✓ contrato del proyecto" || { echo "  ✗ no se encuentra transitions.yml"; ok=0; }; \
	for y in config catalogo escenarios guion; do \
	  $(PY) -c "import yaml,sys; yaml.safe_load(open('$(DEMO)/'+sys.argv[1]+'.yml'))" $$y 2>/dev/null \
	    && echo "  ✓ $$y.yml" || { echo "  ✗ $$y.yml no es YAML válido: corrígelo antes de reiniciar"; ok=0; }; \
	done; \
	[ $$ok = 1 ] || exit 1

up: check
	@mkdir -p $(DEMO)/run $(DEMO)/logs
	@if [ -f $(PID) ] && kill -0 $$(cat $(PID)) 2>/dev/null; then \
	  echo "Ya está arriba (pid $$(cat $(PID))): $(URL)"; exit 0; fi; \
	for p in $(PUERTO) $(PUERTO_CONSOLA); do \
	  if (exec 3<>/dev/tcp/127.0.0.1/$$p) 2>/dev/null; then \
	    echo "El puerto $$p está ocupado por otro proceso. Usar: make up PUERTO=<otro> PUERTO_CONSOLA=<otro>"; exit 1; fi; \
	done; \
	cd $(DEMO)/servidor || exit 1; \
	nohup $(PY) app.py --host $(HOST) --puerto $(PUERTO) --puerto-consola $(PUERTO_CONSOLA) >> $(LOG) 2>&1 & echo $$! > $(PID); \
	for i in $$(seq 1 30); do \
	  curl -sf -o /dev/null $(URL)/api/salud && break; sleep 0.5; \
	  kill -0 $$(cat $(PID)) 2>/dev/null || { echo "No arrancó. Últimas líneas del log:"; tail -n 20 $(LOG); rm -f $(PID); exit 1; }; \
	done; \
	echo "Demo arriba (pid $$(cat $(PID)))"; \
	echo "  en vivo  (se proyecta, solo mira):  $(URL)"; \
	echo "  consola  (el guion y las acciones): $(URL_CONSOLA)"; \
	[ "$(HOST)" = "0.0.0.0" ] && echo "  Atención: visible desde otras máquinas." || true

down:
	@if [ -f $(PID) ] && kill -0 $$(cat $(PID)) 2>/dev/null; then \
	  kill $$(cat $(PID)); for i in $$(seq 1 20); do kill -0 $$(cat $(PID)) 2>/dev/null || break; sleep 0.25; done; \
	  kill -0 $$(cat $(PID)) 2>/dev/null && kill -9 $$(cat $(PID)); echo "Demo abajo."; \
	else \
	  huerfano=$$(pgrep -f "app.py --host [^ ]* --puerto $(PUERTO) "); \
	  if [ -n "$$huerfano" ]; then kill $$huerfano; echo "Demo abajo (pid $$huerfano, sin archivo de pid)."; \
	  else echo "No estaba arriba."; fi; \
	fi; rm -f $(PID)

# Primero se valida: con un archivo roto, la pagina que corre no se baja.
restart: check
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up

# La memoria se recupera al arrancar si es de hace menos de historia_minutos;
# con t=0 se descarta la linea de tiempo, pero el guion y el caso elegido se
# recuperan siempre.
limpio: check
	@$(MAKE) --no-print-directory down
	@f=$(DEMO)/run/memoria.json; if [ -f $$f ]; then \
	  cp $$f $(DEMO)/run/memoria-$$(date +%Y%m%d-%H%M%S).json; \
	  $(PY) -c "import json,sys; d=json.load(open(sys.argv[1])); json.dump({'t': 0, 'guion': d.get('guion'), 'demo': d.get('demo')}, open(sys.argv[1], 'w'))" $$f \
	    && echo "Línea de tiempo vacía; el caso elegido y el guion se conservan."; fi
	@$(MAKE) --no-print-directory up

status:
	@if [ -f $(PID) ] && kill -0 $$(cat $(PID)) 2>/dev/null; then echo "Arriba (pid $$(cat $(PID))) · en vivo $(URL) · consola $(URL_CONSOLA)"; \
	  curl -sf $(URL)/api/salud | $(PY) -c "import json,sys; d=json.load(sys.stdin); \
	  [print('  %-13s %s' % (k, ('ok  %.1f s, hace %s s' % (v['ms']/1000, v.get('antiguedad'))) if v['ok'] else 'FALLA: '+str(v.get('error')))) for k,v in sorted(d['fuentes'].items()) if k!='vista']" \
	  || echo "  no responde en $(URL)"; \
	else echo "Abajo."; fi

logs:
	@tail -n 50 -f $(LOG)
