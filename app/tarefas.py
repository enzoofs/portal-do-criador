"""
app/tarefas.py — Execuções longas (radar, pauta, artigos, rastreamento) em segundo plano.

Uma tarefa por vez: o contador de custo é único no processo, e uma agência
não precisa de duas execuções pagas em paralelo. A tela consulta o progresso
por /api/tarefas/<id>. Execuções reais só começam depois da confirmação na
janela de custo (que chama custos.contador.iniciar com o teto escolhido).
"""

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import custos
import guias
from app import dados
from conteudo import fluxo
from conteudo import pauta as pauta_mod
from radar import cruzamento, executor, rastreador, relatorio

_lock = threading.Lock()
_tarefas: dict[str, "Tarefa"] = {}

# Não chamam IA nem API paga: rodam sem a janela de custo e sem mexer no contador
TAREFAS_GRATIS = {"rastreio"}


class Ocupado(RuntimeError):
    pass


@dataclass
class Tarefa:
    id: str
    tipo: str
    cliente_id: str
    status: str = "rodando"          # rodando | ok | erro
    linhas: list[str] = field(default_factory=list)
    custo_usd: float | None = None
    erro: str | None = None
    inicio: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    fim: str | None = None

    def log(self, texto: str):
        self.linhas.append(texto)

    def to_dict(self):
        return asdict(self)


def em_andamento() -> Tarefa | None:
    return next((t for t in _tarefas.values() if t.status == "rodando"), None)


def obter(tid: str) -> Tarefa | None:
    return _tarefas.get(tid)


def iniciar(tipo: str, cliente_id: str, demo: bool, limite: float, temas: list[int] | None = None,
            repeticoes: int = 1) -> Tarefa:
    with _lock:
        if em_andamento():
            raise Ocupado("Já existe uma execução em andamento. Aguarde terminar.")
        t = Tarefa(id=uuid.uuid4().hex[:10], tipo=tipo, cliente_id=cliente_id)
        _tarefas[t.id] = t
    pago = not demo and tipo not in TAREFAS_GRATIS
    if pago:
        custos.contador.iniciar(limite)  # a janela de confirmação já mostrou a estimativa
    alvo = {"radar": _radar, "pauta": _pauta, "artigos": _artigos, "rastreio": _rastreio}[tipo]
    extra = repeticoes if tipo == "radar" else temas
    threading.Thread(target=_rodar, args=(t, alvo, demo, extra, pago), daemon=True).start()
    return t


def _rodar(t: Tarefa, alvo, demo: bool, temas, pago: bool):
    try:
        alvo(t, demo, temas)
        t.status = "ok"
    except Exception as e:
        t.status, t.erro = "erro", f"{type(e).__name__}: {e}"
        t.log(f"Erro: {t.erro}")
    finally:
        if pago:
            t.custo_usd = custos.contador.resumo()["total_usd"]
            t.log(f"Custo real: US$ {t.custo_usd:.2f}")
            custos.anotar_gasto(t.tipo, t.cliente_id, t.custo_usd)
            custos.contador.autorizado = False  # cada execução paga exige nova confirmação
        t.fim = datetime.now().isoformat(timespec="seconds")


def _radar(t: Tarefa, demo: bool, repeticoes):
    resultado = executor.executar(t.cliente_id, demo=demo, repeticoes=repeticoes or 1, progresso=t.log)
    if not demo:
        resultado["custo"] = custos.contador.resumo()
        Path(resultado["_arquivo"]).write_text(json.dumps(
            {k: v for k, v in resultado.items() if k != "_arquivo"}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    relatorio.salvar(resultado, rastreador.do_run(resultado))
    if not demo:
        escritos = guias.gerar(resultado["cliente"], resultado, rastreador.do_run(resultado))
        t.log(f"{len(escritos)} guias do plano atualizados")
    r = resultado["metricas"]["resumo"]
    t.log(f"Visibilidade: {r['visibilidade']}% ({r['mencoes']}/{r['respostas_descoberta']})")


def _rastreio(t: Tarefa, demo: bool, _extra):
    run = dados.ultimo_radar(t.cliente_id)   # confere também as páginas que as IAs citaram
    r = rastreador.rastrear(dados.cliente(t.cliente_id), demo=demo, progresso=t.log,
                            extras=cruzamento.urls_citadas(run) if run else None)
    rastreador.salvar(r)


def _pauta(t: Tarefa, demo: bool, _temas):
    cliente = dados.cliente(t.cliente_id)
    run = dados.ultimo_radar(t.cliente_id)
    t.log("Montando a pauta a partir do último radar…" if run else "Montando a pauta (sem radar)…")
    p = pauta_mod.gerar_pauta(cliente, run, demo=demo)
    fluxo.atualizar_central(Path(p["_pasta"]), cliente)
    for i, tema in enumerate(p["temas"], start=1):
        t.log(f"  {i}. {tema['titulo']}")


def _artigos(t: Tarefa, demo: bool, temas):
    cliente = dados.cliente(t.cliente_id)
    pasta, _ = dados.pauta(t.cliente_id)
    if not pasta:
        raise RuntimeError("Nenhuma pauta. Gere a pauta primeiro.")
    fluxo.escrever_pauta(pasta, cliente, dados.ultimo_radar(t.cliente_id), temas, progresso=t.log)
