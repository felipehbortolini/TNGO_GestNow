import azure.functions as func

from src.blueprints.acesso import bp as acesso_bp
from src.blueprints.attachments import bp as attachments_bp
from src.blueprints.exports import bp as exports_bp
from src.blueprints.health import bp as health_bp
from src.blueprints.importing import bp as importing_bp
from src.blueprints.nav import bp as nav_bp
from src.modulos.central_acoes.minutes_routes import bp as central_acoes_atas_bp
from src.modulos.central_acoes.panel_routes import bp as central_acoes_painel_bp
from src.modulos.central_acoes.routes import bp as central_acoes_bp
from src.modulos.configuracoes.routes import bp as configuracoes_bp
from src.modulos.financeiro.routes import bp as financeiro_bp
from src.modulos.governanca.lessons_routes import bp as governanca_licoes_bp
from src.modulos.governanca.routes import bp as governanca_bp
from src.modulos.hse.routes import bp as hse_bp
from src.modulos.inicio.routes import bp as inicio_bp
from src.modulos.planejamento.routes import bp as planejamento_bp
from src.modulos.programacao_semanal.routes import bp as programacao_semanal_bp
from src.modulos.qualidade.routes import bp as qualidade_bp
from src.modulos.relatorio.routes import bp as relatorio_bp
from src.modulos.riscos.routes import bp as riscos_bp
from src.modulos.suprimentos.routes import bp as suprimentos_bp

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

app.register_functions(health_bp)
app.register_functions(nav_bp)
app.register_functions(acesso_bp)
app.register_functions(exports_bp)
app.register_functions(attachments_bp)
app.register_functions(importing_bp)
app.register_functions(inicio_bp)
app.register_functions(central_acoes_bp)
app.register_functions(central_acoes_atas_bp)
app.register_functions(central_acoes_painel_bp)
app.register_functions(planejamento_bp)
app.register_functions(programacao_semanal_bp)
app.register_functions(financeiro_bp)
app.register_functions(suprimentos_bp)
app.register_functions(riscos_bp)
app.register_functions(qualidade_bp)
app.register_functions(hse_bp)
app.register_functions(governanca_bp)
app.register_functions(governanca_licoes_bp)
app.register_functions(configuracoes_bp)
app.register_functions(relatorio_bp)
