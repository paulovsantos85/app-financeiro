import flet as ft
import sys
import time

# ==============================================================================
# ETAPA 3: DASHBOARD MOBILE FIRST COM GRÁFICOS DE PIZZA (BRL FORMAT)
# ==============================================================================

MOCK_MODE = False

class DatabaseHandler:
    def __init__(self):
        self.host = "84.247.176.35"
        self.database = "postgres"
        self.user = "postgres"
        # ---------------------------------------------------------
        # ATENÇÃO: CERTIFIQUE-SE QUE ESTA SENHA ESTÁ CORRETA
        self.password = "46b580396f301713ef2e8c56b45d862a" 
        # ---------------------------------------------------------
        self.port = "5432"
        self.conn = None
        
        self.current_user_phone = None
        self.current_user_name = None

    def connect(self):
        if MOCK_MODE:
            return True, "Modo Mock"
        try:
            import psycopg2
            if not self.conn or self.conn.closed:
                self.conn = psycopg2.connect(
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=self.port,
                    connect_timeout=5 
                )
            return True, "Conectado"
        except ImportError:
            return False, "Instale psycopg2-binary"
        except Exception as e:
            return False, str(e)

    def run_diagnostics(self):
        status, msg = self.connect()
        if not status: return f"Falha: {msg}"
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            return f"Tabelas encontradas: {[t[0] for t in cursor.fetchall()]}"
        except Exception as e:
            return f"Erro SQL: {e}"

    def authenticate(self, phone, password):
        if MOCK_MODE:
             self.current_user_phone = "123"
             self.current_user_name = "Mock User"
             return {"success": True, "route": "/dashboard", "message": "Mock"}

        status, msg = self.connect()
        if not status:
            return {"success": False, "message": msg}

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT primeiro_acesso, nome, telefone FROM clientesia WHERE telefone = %s", (phone,))
            user_data = cursor.fetchone()

            if not user_data:
                return {"success": False, "message": "Usuário não encontrado."}

            primeiro_acesso, nome, _ = user_data
            
            if primeiro_acesso:
                if phone == password: 
                    self.current_user_phone = phone
                    self.current_user_name = nome
                    return {"success": True, "route": "/change_password", "message": "Primeiro acesso."}
                else:
                    return {"success": False, "message": "Use seu telefone como senha."}
            
            cursor.execute("SELECT * FROM clientesia WHERE telefone = %s AND senha = %s", (phone, password))
            if cursor.fetchone():
                self.current_user_phone = phone
                self.current_user_name = nome
                return {"success": True, "route": "/dashboard", "message": "Login realizado."}
            else:
                return {"success": False, "message": "Senha incorreta."}

        except Exception as e:
            return {"success": False, "message": f"Erro SQL: {str(e)}"}

    def update_password(self, new_password):
        if MOCK_MODE: return True
        if not self.connect() or not self.current_user_phone: return False
        try:
            cursor = self.conn.cursor()
            query = "UPDATE clientesia SET senha = %s, primeiro_acesso = FALSE WHERE telefone = %s"
            cursor.execute(query, (new_password, self.current_user_phone))
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            return False

    def get_summary(self):
        """Busca os totais de Receita, Despesa e Saldos."""
        default = {"balance": 0.0, "income": 0.0, "expense": 0.0, "initial_balance": 0.0}
        if MOCK_MODE: return {"balance": 15455.50, "income": 20000.00, "expense": 4544.50, "initial_balance": 1000.00}
        
        if not self.connect() or not self.current_user_phone: return default

        try:
            cursor = self.conn.cursor()
            phone = self.current_user_phone
            
            # Receitas
            cursor.execute("SELECT COALESCE(sum(receitas), 0) FROM clientesia WHERE telefone = %s", (phone,))
            income = float(cursor.fetchone()[0])

            # Despesas
            cursor.execute("SELECT COALESCE(sum(despesas), 0) FROM clientesia WHERE telefone = %s", (phone,))
            expense = float(cursor.fetchone()[0])

            # Saldo Atual
            cursor.execute("SELECT COALESCE(sum(saldo_atual), 0) FROM clientesia WHERE telefone = %s", (phone,))
            balance = float(cursor.fetchone()[0])

            # Saldo Inicial (Adicionado conforme solicitado)
            cursor.execute("SELECT COALESCE(sum(saldo_inicial), 0) FROM clientesia WHERE telefone = %s", (phone,))
            initial_balance = float(cursor.fetchone()[0])
            
            return {
                "balance": balance, 
                "income": income, 
                "expense": expense, 
                "initial_balance": initial_balance
            }
        except Exception as e:
            print(f"Erro Summary: {e}")
            return default

    def get_transactions(self):
        """Busca lista de transações recentes."""
        if MOCK_MODE: return [{"desc": "Teste", "val": 100, "type": "in"}]
        
        if not self.connect() or not self.current_user_phone: return []

        try:
            cursor = self.conn.cursor()
            query = "SELECT nome, receitas, despesas FROM clientesia WHERE telefone = %s LIMIT 10"
            cursor.execute(query, (self.current_user_phone,))
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                nome = row[0]
                receita = float(row[1] or 0)
                despesa = float(row[2] or 0)
                
                if receita > 0:
                    val = receita
                    t_type = "in"
                    desc = f"Receita - {nome}"
                else:
                    val = despesa
                    t_type = "out"
                    desc = f"Despesa - {nome}"
                
                if val > 0:
                    result.append({"desc": desc, "val": val, "type": t_type})
            return result
        except Exception as e:
            print(f"Erro Transacoes: {e}")
            return []

db = DatabaseHandler()

# ==============================================================================
# UI - SISTEMA DE NAVEGAÇÃO
# ==============================================================================

def main(page: ft.Page):
    print("Iniciando App...")
    page.title = "App Financeiro"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#f5f7fa"
    page.scroll = "auto"
    
    # Configuração Mobile: Ajusta o padding da janela
    page.padding = 0

    # Helper para formatar moeda brasileira (R$ 1.234,56)
    def format_currency(value):
        try:
            # Formata estilo US primeiro: 1,234.56
            us_fmt = f"R$ {value:,.2f}"
            # Troca , por X, . por , e X por .
            return us_fmt.replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return f"R$ {value}"

    def navigate_to(route):
        print(f"Navegando para: {route}")
        page.clean()
        if route == "/login": page.add(create_login_view())
        elif route == "/change_password": page.add(create_change_password_view())
        elif route == "/dashboard": page.add(create_dashboard_view())
        page.update()

    # --- TELA 1: LOGIN ---
    def create_login_view():
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        user_input = ft.TextField(label="Telefone", width=300, border_radius=10)
        pass_input = ft.TextField(label="Senha", password=True, can_reveal_password=True, width=300, border_radius=10)
        result_text = ft.Text("", size=14)

        def on_login(e):
            result_text.value = "Entrando..."
            result_text.color = "blue"
            page.update()
            res = db.authenticate(user_input.value, pass_input.value)
            if res["success"]:
                navigate_to(res["route"])
            else:
                result_text.value = res["message"]
                result_text.color = "red"
                page.update()

        return ft.Container(
            content=ft.Column([
                ft.Text("🔒", size=40),
                ft.Text("Acesso Financeiro", size=20, weight="bold"),
                ft.Divider(),
                user_input, pass_input,
                ft.ElevatedButton("Entrar", on_click=on_login, width=300, bgcolor="#1E88E5", color="white"),
                result_text
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=30, bgcolor="white", border_radius=15, alignment=ft.Alignment(0, 0),
            margin=ft.margin.all(20)
        )

    # --- TELA 2: ALTERAR SENHA ---
    def create_change_password_view():
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        new_pass = ft.TextField(label="Nova Senha", password=True, width=300)
        confirm_pass = ft.TextField(label="Confirmar Senha", password=True, width=300)
        msg = ft.Text("")

        def on_save(e):
            if new_pass.value != confirm_pass.value:
                msg.value = "Senhas não coincidem"; msg.color = "red"; page.update(); return
            
            if db.update_password(new_pass.value):
                msg.value = "Sucesso!"; msg.color = "green"; page.update(); time.sleep(1); navigate_to("/dashboard")
            else:
                msg.value = "Erro no banco"; msg.color = "red"; page.update()

        return ft.Container(
            content=ft.Column([
                ft.Text("🔑", size=40),
                ft.Text("Definir Senha", size=20, weight="bold"),
                new_pass, confirm_pass,
                ft.ElevatedButton("Salvar", on_click=on_save, width=300, bgcolor="#43A047", color="white"),
                msg
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=30, bgcolor="white", border_radius=15, alignment=ft.Alignment(0, 0),
            margin=ft.margin.all(20)
        )

    # --- TELA 3: DASHBOARD ---
    def create_dashboard_view():
        page.vertical_alignment = ft.MainAxisAlignment.START
        
        # 1. Busca Dados
        summary = db.get_summary()
        transactions = db.get_transactions()
        
        # 2. Helper para Gráficos
        def make_chart(title, data_points):
            try:
                sections = []
                for dp in data_points:
                    if dp[1] > 0:
                        # Formata o valor no label do gráfico
                        val_fmt = format_currency(dp[1]).replace("R$ ", "")
                        sections.append(
                            ft.PieChartSection(
                                value=dp[1],
                                color=dp[2],
                                title=f"{val_fmt}",
                                title_style=ft.TextStyle(size=10, color="white", weight="bold"),
                                radius=40
                            )
                        )
                
                if not sections:
                    chart_content = ft.Text("Sem dados", size=12, color="grey")
                else:
                    chart_content = ft.PieChart(
                        sections=sections,
                        sections_space=2,
                        center_space_radius=30,
                        height=150
                    )
                
                return ft.Container(
                    content=ft.Column([
                        ft.Text(title, size=14, weight="bold"),
                        chart_content
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=15, bgcolor="white", border_radius=15,
                    border=ft.border.all(1, "#EEEEEE")
                )

            except AttributeError:
                return make_comparison_bar_fallback(title, data_points)

        def make_comparison_bar_fallback(title, data_points):
            rows = []
            for dp in data_points:
                rows.append(
                    ft.Column([
                        # Aplica formato brasileiro
                        ft.Text(f"{dp[0]}: {format_currency(dp[1])}", size=10, color="grey"),
                        ft.Container(width=100, height=8, bgcolor=dp[2], border_radius=4)
                    ], spacing=2)
                )
            return ft.Container(
                content=ft.Column([ft.Text(title, size=12, weight="bold")] + rows, spacing=10),
                padding=15, bgcolor="white", border_radius=15, border=ft.border.all(1, "#EEEEEE")
            )

        # Configuração dos Gráficos Solicitados
        chart1 = make_chart("Receita vs Despesa", [
            ("Rec", summary['income'], "#43A047"), 
            ("Desp", summary['expense'], "#E53935")
        ])
        
        chart2 = make_chart("S. Inic vs Atual", [
            ("Inic", summary['initial_balance'], "#1E88E5"), 
            ("Atual", summary['balance'], "#4FC3F7")
        ])

        chart3 = make_chart("S. Inic vs Desp", [
            ("Inic", summary['initial_balance'], "#1E88E5"), 
            ("Desp", summary['expense'], "#E53935")
        ])

        chart4 = make_chart("S. Atual vs Desp", [
            ("Atual", summary['balance'], "#4FC3F7"), 
            ("Desp", summary['expense'], "#E53935")
        ])

        # 3. Cards de Texto (Scroll Horizontal Mobile)
        def make_card(title, value, color_hex, icon_emoji):
            return ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text(icon_emoji, size=20), ft.Text(title, size=12, color="grey")], alignment=ft.MainAxisAlignment.START),
                    # Aplica formato brasileiro
                    ft.Text(format_currency(value), size=18, weight="bold", color="#333333")
                ], spacing=5),
                width=160, height=100, bgcolor="white", border_radius=15, padding=15,
                border=ft.border.only(left=ft.BorderSide(5, color_hex))
            )

        card_balance = make_card("Saldo Atual", summary['balance'], "#1E88E5", "💰") 
        card_income = make_card("Receitas", summary['income'], "#43A047", "📈")   
        card_expense = make_card("Despesas", summary['expense'], "#E53935", "📉") 
        card_initial = make_card("Saldo Inicial", summary['initial_balance'], "#FFA000", "💼")

        # 4. Lista de Transações
        trans_list = ft.Column(spacing=10)
        if not transactions:
            trans_list.controls.append(ft.Text("Nenhuma transação recente.", color="grey"))
        else:
            for t in transactions:
                val_color = "#43A047" if t['type'] == 'in' else "#E53935"
                icon = "⬇️" if t['type'] == 'in' else "⬆️"
                row = ft.Container(
                    content=ft.Row([
                        ft.Row([
                            ft.Container(content=ft.Text(icon), bgcolor="#F5F5F5", padding=10, border_radius=10),
                            ft.Column([
                                ft.Text(t['desc'], weight="bold", size=14, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text("Transação", size=10, color="grey")
                            ])
                        ]),
                        # Aplica formato brasileiro
                        ft.Text(format_currency(t['val']), color=val_color, weight="bold", size=12)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10, bgcolor="white", border_radius=10,
                    border=ft.border.only(bottom=ft.BorderSide(1, "#EEEEEE"))
                )
                trans_list.controls.append(row)

        # 5. Montagem Final Responsiva
        return ft.Column([
            # Topo
            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(f"Olá, {db.current_user_name}", size=18, weight="bold"),
                        ft.Text("Dashboard", size=12, color="grey")
                    ]),
                    ft.Container(
                        content=ft.Text("🚪 Sair", size=14, color="red", weight="bold"),
                        on_click=lambda _: navigate_to("/login"),
                        padding=8, border_radius=8, bgcolor="#FFEBEE"
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=20, bgcolor="white"
            ),
            
            # Cards de Valores
            ft.Container(
                content=ft.Row([card_balance, card_income, card_expense, card_initial], scroll="hidden"),
                padding=ft.padding.only(left=20, right=20, top=10, bottom=10)
            ),

            # Área de Gráficos (RESPONSIVO: 1 coluna no celular, 2 no PC)
            ft.Container(
                content=ft.Column([
                    ft.Text("Análise Comparativa", size=16, weight="bold"),
                    
                    # ResponsiveRow faz a mágica do Mobile First
                    ft.ResponsiveRow([
                        ft.Column([chart1], col={"xs": 12, "md": 6}),
                        ft.Column([chart2], col={"xs": 12, "md": 6}),
                        ft.Column([chart3], col={"xs": 12, "md": 6}),
                        ft.Column([chart4], col={"xs": 12, "md": 6}),
                    ], run_spacing=10)
                ], spacing=10),
                padding=ft.padding.only(left=20, right=20, bottom=10)
            ),
            
            # Lista
            ft.Container(
                content=ft.Column([
                    ft.Text("Últimas Transações", size=16, weight="bold"),
                    trans_list
                ]),
                padding=20, expand=True
            )
        ], expand=True, scroll="auto")

    navigate_to("/login")

ft.app(target=main)