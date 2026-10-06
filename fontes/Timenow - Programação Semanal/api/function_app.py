"""Registro dos blueprints da Programação Semanal de Serviços.

Cada módulo de ``src/blueprints/`` agrupa as rotas de um assunto. Página
nova é blueprint novo aqui e um item em ``nav.ITENS``.
"""

import azure.functions as func

from src.blueprints.ambientes import bp as ambientes_bp
from src.blueprints.atividades import bp as atividades_bp
from src.blueprints.colaboradores import bp as colaboradores_bp
from src.blueprints.configuracoes import bp as configuracoes_bp
from src.blueprints.dados_api import bp as dados_api_bp
from src.blueprints.dashboard import bp as dashboard_bp
from src.blueprints.exportacao import bp as exportacao_bp
from src.blueprints.governanca import bp as governanca_bp
from src.blueprints.health import bp as health_bp
from src.blueprints.importacao import bp as importacao_bp
from src.blueprints.nav import bp as nav_bp
from src.blueprints.programacao import bp as programacao_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_functions(health_bp)
app.register_functions(dados_api_bp)
app.register_functions(ambientes_bp)
app.register_functions(nav_bp)
app.register_functions(programacao_bp)
app.register_functions(atividades_bp)
app.register_functions(dashboard_bp)
app.register_functions(importacao_bp)
app.register_functions(exportacao_bp)
app.register_functions(governanca_bp)
app.register_functions(configuracoes_bp)
app.register_functions(colaboradores_bp)
