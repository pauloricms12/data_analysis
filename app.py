import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configuração da página do Streamlit para usar a tela inteira
st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    """Carrega os dados dos arquivos excel e os armazena em cache."""
    df_pedido = pd.read_excel('data/pedidos.xlsx')
    df_itens = pd.read_excel('data/itens_supply.xlsx', sheet_name='Itens')
    df_supply = pd.read_excel('data/itens_supply.xlsx', sheet_name='Supply')
    return df_pedido, df_itens, df_supply

def add_back_to_home_button():
    """Adiciona um botão para voltar à página inicial."""
    if st.button("⬅️ Voltar à Página Inicial"):
        st.session_state.page = 'home'
        st.rerun() # Força a re-execução do script para atualizar a página

# --- FUNÇÕES DAS PÁGINAS DE ANÁLISE ---

def page_pedidos_por_dia(df_pedido):
    
    add_back_to_home_button()
    st.markdown(f"""
        <div style="text-align: center; padding-top: 20px;">
            <p style="font-size: 40px; margin-bottom: 0;">Distribuição dos Pedidos</p>
        </div>
        """, unsafe_allow_html=True)
    
    df_plot = df_pedido.set_index('created_at')
    serie_pedidos = df_plot.resample('D')['id'].nunique()
    
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.set_style("whitegrid", {"grid.color": ".8", "grid.linestyle": "--"})
    
    _, col0, _ = st.columns([1, 3, 1])
    with col0:

        sns.lineplot(
            data=serie_pedidos.reset_index(),
            x='created_at',
            y='id',
            linewidth=2.5,
            marker='o',
            markersize=6,
            ax=ax
        )

        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d'))

        media = serie_pedidos.mean()
        ax.axhline(y=media, color='darkorange', linestyle='--', alpha=0.8, 
                label=f'Média: {media:.1f} pedidos/dia')

        ax.set_title('Pedidos por dia', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Dia', fontsize=12, fontweight='bold')
        ax.set_ylabel('Número de Pedidos', fontsize=12, fontweight='bold')
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig, width='stretch')

    st.write("---")

    # --- NOVO: Métrica de Total de Pedidos e Tabela de Dados ---

    # Usando colunas para centralizar a métrica e mostrar a tabela ao lado
    col1, col2 = st.columns(2)

    with col1:
        # Calcula o total de pedidos
        total_pedidos = serie_pedidos.sum()
        
        # Markdown para exibir o total de pedidos de forma customizada
        st.markdown(f"""
        <div style="text-align: center; padding-top: 20px;">
            <p style="font-size: 40px; margin-bottom: 0;">Total de Pedidos no Período</p>
            <p style="font-size: 62px; font-weight: bold;">{total_pedidos}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.subheader("Dados Diários")
        
        df_tabela = serie_pedidos.reset_index()
        df_tabela.columns = ['Dia', 'Quantidade de Pedidos']

        df_tabela['Dia'] = df_tabela['Dia'].dt.strftime('%d/%m/%Y')
        
        # Usa st.dataframe para uma tabela com barra de rolagem
        st.dataframe(df_tabela, height=500, width='stretch')

def page_analise_descontos(df_pedido, df_itens):
    """Renderiza a página de análise de descontos."""
    add_back_to_home_button()
    st.header("Análise de Descontos e Correlação com Vendas")

    st.sidebar.header("Opções de Análise de Desconto")

    # Checkbox para controlar a remoção de outliers
    desconsiderar_outliers = st.sidebar.checkbox("Desconsiderar Outliers de Vendas (dias com > 95% de pedidos)")

    # --- CÁLCULOS ---
    soma_dos_itens_por_pedido = df_itens.groupby('order_id')['price'].sum().reset_index()
    soma_dos_itens_por_pedido.rename(columns={'price': 'soma_precos_itens'}, inplace=True)

    df_financeiro_pedidos = df_pedido.merge(soma_dos_itens_por_pedido, left_on='id', right_on='order_id', how='left')
    df_financeiro_pedidos['soma_dos_itens_e_frete'] = df_financeiro_pedidos['soma_precos_itens'].fillna(0) + df_financeiro_pedidos['Frete Cobrado do Cliente (R$)']
    
    # Evitar divisão por zero ou valores negativos que geram descontos > 100%
    df_financeiro_pedidos = df_financeiro_pedidos[df_financeiro_pedidos['soma_dos_itens_e_frete'] > 0]
    
    termo_divisao = df_financeiro_pedidos['Valor de NF (R$)'] / df_financeiro_pedidos['soma_dos_itens_e_frete']
    df_financeiro_pedidos['desconto_calculado'] = (1 - termo_divisao) * 100

    # Resample dos dados por dia
    df_plot = df_financeiro_pedidos.set_index('created_at')
    serie_desconto = df_plot.resample('D')['desconto_calculado'].mean()
    serie_pedidos = df_plot.resample('D')['id'].nunique()

    # --- LÓGICA DE FILTRO DE OUTLIERS ---
    if desconsiderar_outliers:
        limite_outlier = serie_pedidos.quantile(0.98)
        dias_originais = len(serie_pedidos)
        
        # Filtra os dados com base no limite de pedidos
        serie_pedidos_final = serie_pedidos[serie_pedidos <= limite_outlier]
        serie_desconto_final = serie_desconto[serie_pedidos <= limite_outlier]
        
        dias_removidos = dias_originais - len(serie_pedidos_final)
        st.info(f"Outliers desconsiderados. {dias_removidos} dia(s) com mais de {limite_outlier:.0f} pedidos foram removidos da análise.")
    else:
        serie_pedidos_final = serie_pedidos
        serie_desconto_final = serie_desconto

    # --- PLOTS E MÉTRICAS ---
    col1, col2 = st.columns(2)

    with col1:
        fig1, ax1 = plt.subplots(figsize=(8, 5))
        sns.lineplot(data=serie_desconto_final.reset_index(), x='created_at', y='desconto_calculado',
                     linewidth=2.5, marker='o', markersize=6, ax=ax1)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'))
        ax1.set_title('Desconto médio por dia', fontsize=14, fontweight='bold', pad=20)
        ax1.set_xlabel('Dia', fontsize=12)
        ax1.set_ylabel('Valor do desconto (%)', fontsize=12)
        media_desconto = serie_desconto_final.mean()
        ax1.axhline(y=media_desconto, color='darkorange', linestyle='--', alpha=0.8, 
                   label=f'Média: {media_desconto:.2f}%')
        ax1.legend()
        plt.tight_layout()
        st.pyplot(fig1, use_container_width=True)

    with col2:
        fig2, ax2 = plt.subplots(figsize=(8, 5))
        sns.regplot(x=serie_desconto_final, y=serie_pedidos_final, ax=ax2, ci=None, line_kws={"color":"red","linestyle":"--"})
        ax2.set_title('Correlação Pedidos vs Desconto', fontsize=14, fontweight='bold', pad=20)
        ax2.set_xlabel('Desconto médio (%)', fontsize=12)
        ax2.set_ylabel('Número de Pedidos', fontsize=12)
        plt.tight_layout()
        st.pyplot(fig2, use_container_width=True)
    
    # Calcula a correlação com os dados finais (filtrados ou não)
    corr = pd.Series.corr(serie_desconto_final, serie_pedidos_final, method='pearson')
    st.markdown(f"""
<div style="text-align: center;">
    <p style="font-size: 20px; margin-bottom: 0;">Coeficiente de Correlação de Pearson</p>
    <p style="font-size: 12px; margin-bottom: 0;">Entre Pedidos e Desconto Médio por dia</p>
    <p style="font-size: 36px; font-weight: bold;">{corr:.3f}</p>
</div>
""", unsafe_allow_html=True)


def page_analise_faturamento(df_pedido, df_itens):
    """Renderiza a página de análise de faturamento."""
    add_back_to_home_button()
    st.header("Análise de Faturamento por Categoria e Produto")

    # --- NOVO: Filtro de Data na Barra Lateral ---
    st.sidebar.header("Opções de Análise")
    
    # Garante que a coluna de data esteja no formato datetime
    df_pedido['created_at'] = pd.to_datetime(df_pedido['created_at'])

    # Opção para filtrar por um dia específico
    filtrar_por_data = st.sidebar.checkbox("Filtrar por dia específico")
    
    df_pedido_filtrado = df_pedido.copy()
    
    if filtrar_por_data:
        # Define os limites do seletor de data
        min_date = df_pedido['created_at'].min().date()
        max_date = df_pedido['created_at'].max().date()
        
        selected_date = st.sidebar.date_input(
            "Selecione o dia",
            value=max_date,  # Padrão para o dia mais recente
            min_value=min_date,
            max_value=max_date
        )
        # Filtra o DataFrame para o dia selecionado
        df_pedido_filtrado = df_pedido[df_pedido['created_at'].dt.date == selected_date]

    # --- Cálculos de Faturamento (usando o DataFrame filtrado) ---
    soma_dos_itens_por_pedido = df_itens.groupby('order_id')['price'].sum().reset_index()
    soma_dos_itens_por_pedido.rename(columns={'price': 'soma_precos_itens'}, inplace=True)

    df_financeiro_pedidos = df_pedido_filtrado.merge(soma_dos_itens_por_pedido, left_on='id', right_on='order_id', how='left')
    df_financeiro_pedidos['soma_dos_itens_e_frete'] = df_financeiro_pedidos['soma_precos_itens'].fillna(0) + df_financeiro_pedidos['Frete Cobrado do Cliente (R$)']

    # Evita divisão por zero
    df_financeiro_pedidos = df_financeiro_pedidos[df_financeiro_pedidos['soma_dos_itens_e_frete'] > 0]
    
    termo_divisao = df_financeiro_pedidos['Valor de NF (R$)'] / df_financeiro_pedidos['soma_dos_itens_e_frete']
    df_financeiro_pedidos['desconto_calculado'] = (1 - termo_divisao) * 100
    df_financeiro_pedidos = df_financeiro_pedidos[(df_financeiro_pedidos['desconto_calculado'] >= 0) & (df_financeiro_pedidos['desconto_calculado'] <= 100)]
    
    df_financeiro_itens = df_itens.merge(df_financeiro_pedidos[['order_id', 'desconto_calculado']], on='order_id', how='left')
    
    # Filtra itens que não pertencem ao período de datas selecionado
    if not df_financeiro_pedidos.empty:
        df_financeiro_itens = df_financeiro_itens[df_financeiro_itens['order_id'].isin(df_financeiro_pedidos['order_id'])]
    else:
        st.warning("Não há dados de faturamento para o dia selecionado.")
        return # Encerra a execução da função se não houver dados

    # --- Opções de Visualização ---
    st.sidebar.header("Opções de Faturamento")
    top_x = st.sidebar.slider("Selecione o Top X para visualizar:", min_value=5, max_value=50, value=10)
    calcular_com_desconto = st.sidebar.checkbox("Calcular faturamento líquido (considerando desconto)")

    if calcular_com_desconto:
        st.info("Visualizando faturamento líquido estimado (preço do item - desconto médio do item).")
        df_financeiro_itens['faturamento'] = df_financeiro_itens['price'] * (1 - df_financeiro_itens['desconto_calculado']/100)
    else:
        st.info("Visualizando faturamento bruto (baseado apenas no preço do item).")
        df_financeiro_itens['faturamento'] = df_financeiro_itens['price']

    preco_por_categoria = df_financeiro_itens.groupby('material_category')['faturamento'].sum().sort_values(ascending=False)
    preco_por_nome = df_financeiro_itens.groupby('material_name')['faturamento'].sum().sort_values(ascending=False)

    st.markdown(f"""
        <div style="text-align: center; padding-top: 10px;">
            <p style="font-size: 20px; margin-bottom: 0;">Faturamento Total</p>
            <p style="font-size: 32px; font-weight: bold;">R$ {df_pedido_filtrado['Valor de NF (R$)'].sum():,.2f}</p>
        </div>
        """, unsafe_allow_html=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(25, 12))

    # --- Gráfico da Esquerda (Categorias) ---
    # Plote no primeiro eixo (ax1)
    sns.barplot(x=preco_por_categoria.head(top_x).values, y=preco_por_categoria.head(top_x).index, ax=ax1, orient='h')
    ax1.bar_label(ax1.containers[0], fmt='R$ %.0f', label_type='center', color='white', fontweight='bold')
    ax1.set_xlabel('Faturamento (R$)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Categoria', fontsize=12, fontweight='bold')
    ax1.set_title(f'Top {top_x} Categorias por Faturamento', fontsize=14, fontweight='bold')

    # --- Gráfico da Direita (Produtos) ---
    # Plote no segundo eixo (ax2)
    sns.barplot(x=preco_por_nome.head(top_x).values, y=preco_por_nome.head(top_x).index, ax=ax2, orient='h')
    ax2.bar_label(ax2.containers[0], fmt='R$ %.0f', label_type='center', color='white', fontweight='bold')
    ax2.set_ylabel('Nome', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Faturamento (R$)', fontsize=12, fontweight='bold')
    ax2.set_title(f'Top {top_x} Produtos por Faturamento', fontsize=14, fontweight='bold')

    # 2. Use fig.tight_layout() para ajustar o espaçamento automaticamente
    # O parâmetro 'pad' adiciona um pouco de espaço entre os gráficos
    fig.tight_layout(pad=4.0)

    # 3. Exiba a figura inteira no Streamlit (fora das colunas)
    st.pyplot(fig, width='stretch')

    col1, col2 = st.columns(2)

    with col1:
       
        total_faturamento_cat = preco_por_categoria.sum()
        st.markdown(f"""
        <div style="text-align: center; padding-top: 10px;">
            <p style="font-size: 20px; margin-bottom: 0;">Faturamento Total Estimado (Categorias)</p>
            <p style="font-size: 32px; font-weight: bold;">R$ {total_faturamento_cat:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)

        st.write("---")
        st.write("**Faturamento Detalhado por Categoria**")
        df_tabela_cat = preco_por_categoria.reset_index().round(2)
        df_tabela_cat.columns = ['Categoria', 'Faturamento (R$)']
        st.dataframe(df_tabela_cat, height=300, width='stretch')

        st.write("---")
        st.write("**Ticket Médio por Categoria**")

        # Calcula o número de pedidos únicos por categoria
        pedidos_por_categoria = df_financeiro_itens.groupby('material_category')['order_id'].nunique()

        # Calcula o ticket médio (Faturamento Total / Número de Pedidos Únicos)
        # Fillna(0) caso uma categoria não tenha pedidos, evitando erros.
        ticket_medio_categoria = (preco_por_categoria / pedidos_por_categoria).round(2)

        # Prepara a tabela para exibição
        df_ticket_cat = ticket_medio_categoria.sort_values(ascending=False).reset_index()
        df_ticket_cat.columns = ['Categoria', 'Ticket Médio (R$)']

        st.dataframe(df_ticket_cat, height=300, width='stretch')


    with col2:

        # --- NOVO: Total e Tabela de Faturamento por Produto ---
        total_faturamento_prod = preco_por_nome.sum()
        st.markdown(f"""
        <div style="text-align: center; padding-top: 10px;">
            <p style="font-size: 20px; margin-bottom: 0;">Faturamento Total Estimado (Produtos)</p>
            <p style="font-size: 32px; font-weight: bold;">R$ {total_faturamento_prod:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)

        st.write("---")
        st.write("**Faturamento Detalhado por Produto**")
        df_tabela_prod = preco_por_nome.reset_index().round(2)
        df_tabela_prod.columns = ['Produto', 'Faturamento (R$)']
        st.dataframe(df_tabela_prod, height=300, width='stretch')

        st.write("---")
        st.write("**Ticket Médio por Produto**")

        # Calcula o número de pedidos únicos por produto
        pedidos_por_produto = df_financeiro_itens.groupby('material_name')['order_id'].nunique()

        # Calcula o ticket médio (Faturamento Total / Número de Pedidos Únicos)
        ticket_medio_produto = (preco_por_nome / pedidos_por_produto).round(2)

        # Prepara a tabela para exibição
        df_ticket_prod = ticket_medio_produto.sort_values(ascending=False).reset_index()
        df_ticket_prod.columns = ['Produto', 'Ticket Médio (R$)']

        st.dataframe(df_ticket_prod, height=300, width='stretch')

def page_analise_cancelamento(df_pedido, df_itens, df_supply):
    """Renderiza a página de análise de correlação entre supply e cancelamentos."""
    add_back_to_home_button()
    st.header("Análise de Causas de Cancelamento")
    st.write("Esta análise investiga a correlação entre problemas de supply (estoque zerado ou crítico) e o cancelamento de pedidos.")

    # --- CONTROLES NA BARRA LATERAL ---
    st.sidebar.header("Opções de Análise")
    X = st.sidebar.slider(
        "Defina o Top X para considerar como 'Estoque Crítico':",
        min_value=5, max_value=100, value=20
    )

    # --- CÁLCULOS E PREPARAÇÃO DE DADOS ---

    # 1. Calcular o estoque total por produto
    df_estoque_total = df_supply.groupby('material_id')['quantity'].sum().reset_index()

    # 2. Calcular a cobertura de estoque para definir o que é "crítico"
    df_pedido.index = pd.to_datetime(df_pedido.index)
    vendas_totais = df_itens['material_id'].value_counts().reset_index()
    vendas_totais.columns = ['material_id', 'total_vendido']
    num_dias = (df_pedido.index.max() - df_pedido.index.min()).days + 1
    vendas_totais['venda_media_diaria'] = vendas_totais['total_vendido'] / num_dias
    
    df_cobertura = pd.merge(df_estoque_total, vendas_totais, on='material_id', how='left').fillna(0)
    df_cobertura['dias_de_estoque'] = np.where(
        df_cobertura['venda_media_diaria'] > 0,
        df_cobertura['quantity'] / df_cobertura['venda_media_diaria'], np.inf
    )
    
    # Lista de IDs dos materiais em estado crítico
    df_criticos = df_cobertura.query('dias_de_estoque > 0').sort_values('dias_de_estoque').head(X)
    critical_ids = df_criticos['material_id'].unique()

    # 3. Criar o DataFrame de análise principal
    df_itens_com_estoque_total = pd.merge(df_itens, df_estoque_total, on='material_id', how='left').fillna(0)
    
    # Garante que o nome da coluna de ID está padronizado para o merge
    if 'id' in df_pedido.columns and 'order_id' not in df_pedido.columns:
        df_pedido.rename(columns={'id': 'order_id'}, inplace=True)
        
    df_full = pd.merge(df_itens_com_estoque_total, df_pedido[['order_id', 'Status do Pedido']], on='order_id', how='left')

    # 4. Adicionar as flags de 'estoque_zerado' e 'estoque_critico'
    df_full['estoque_zerado'] = (df_full['quantity'] == 0).astype(int)
    df_full['estoque_critico'] = df_full['material_id'].isin(critical_ids).astype(int)

    # --- SEÇÃO 1: CORRELAÇÃO ENTRE ESTOQUE E CANCELAMENTOS ---
    st.subheader("Impacto do Status do Estoque nos Pedidos")
    
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Ruptura de Estoque (Estoque Zerado)**")
        # Agrupar e calcular a taxa de ruptura
        df_taxa_ruptura = df_full.groupby('Status do Pedido')['estoque_zerado'].mean().reset_index()
        df_taxa_ruptura['estoque_zerado'] *= 100
        df_taxa_ruptura.rename(columns={'estoque_zerado': 'Taxa de Ruptura (%)'}, inplace=True)

        # Plotar o gráfico comparativo
        fig1, ax1 = plt.subplots(figsize=(8, 6))
        sns.barplot(data=df_taxa_ruptura, x='Status do Pedido', y='Taxa de Ruptura (%)', ax=ax1)
        ax1.set_title('Taxa de Estoque Zerado por Status do Pedido', fontweight='bold')
        ax1.set_xlabel('')
        ax1.set_ylabel('% de Itens com Estoque Zerado')
        ax1.bar_label(ax1.containers[0], fmt='%.1f%%')
        st.pyplot(fig1, width='stretch')

        st.info("Em cada Estado do item na Supply Chain, a quantidade de Produtos com Estoque Crítico.")

    with col2:
        st.write(f"**Estoque Crítico (Top {X} com menor cobertura)**")
        # Agrupar e calcular a taxa de criticidade
        df_taxa_critico = df_full.groupby('Status do Pedido')['estoque_critico'].mean().reset_index()
        df_taxa_critico['estoque_critico'] *= 100
        df_taxa_critico.rename(columns={'estoque_critico': f'Taxa de Estoque Crítico (%)'}, inplace=True)

        # Plotar o gráfico comparativo
        fig2, ax2 = plt.subplots(figsize=(8, 6))
        sns.barplot(data=df_taxa_critico, x='Status do Pedido', y=f'Taxa de Estoque Crítico (%)', ax=ax2)
        ax2.set_title(f'Taxa de Estoque Crítico por Status do Pedido', fontweight='bold')
        ax2.set_xlabel('')
        ax2.set_ylabel(f'% de Itens em Estoque Crítico')
        ax2.bar_label(ax2.containers[0], fmt='%.1f%%')
        st.pyplot(fig2, width='stretch')

        st.info("Em cada Estado do item na Supply Chain, a quantidade de Produtos Zerados.")

    st.write("---")

    # --- SEÇÃO 2: ANÁLISE DE VOLUME DE CANCELAMENTOS ---
    st.subheader("Análise de Volume: O Que Está Sendo Mais Cancelado?")
    
    # Usar o aasm_state para filtrar os itens cancelados, como no seu código original
    df_canceled = df_itens.query("aasm_state == 'canceled'")
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.write("**Categorias com Mais Cancelamentos**")
        # Gráfico de barras para categorias com mais cancelamentos
        fig3, ax3 = plt.subplots(figsize=(8, 8))
        sns.barplot(df_canceled.value_counts('material_category').reset_index(),
                    x='count', y='material_category', ax=ax3)
        ax3.set_title('Volume de Cancelamentos por Categoria', fontweight='bold')
        ax3.set_xlabel('Número de Itens Cancelados')
        ax3.set_ylabel('')

        ax3.bar_label(ax3.containers[0])
        st.pyplot(fig3, width='stretch')
    
    with col4:
        st.write("**Produtos com Mais Cancelamentos**")
        df_cancel_prod = df_canceled.value_counts(['material_name', 'material_category']).reset_index()
        df_cancel_prod.columns = ['Produto', 'Categoria', 'Número de Cancelamentos']
        df_cancel_prod = df_cancel_prod[['Produto', 'Categoria', 'Número de Cancelamentos']]
        st.dataframe(df_cancel_prod, height=650, width='stretch')


def page_analise_estoque(df_pedido, df_itens, df_supply):
    """Renderiza a página de análise de estoque."""
    add_back_to_home_button()

    st.header("Análise de Estoque Crítico e Rupturas")
    st.write("Esta página analisa a saúde do estoque, identificando produtos com baixa cobertura (próximos da ruptura) e a distribuição desses itens nos centros de inventário.")

    # --- CONTROLES INTERATIVOS NA BARRA LATERAL ---
    st.sidebar.header("Opções de Análise de Estoque")
    X = st.sidebar.slider(
        "Selecione o número de itens críticos para analisar (Top X):",
        min_value=5,
        max_value=50,
        value=15  # Um valor padrão
    )

    # --- CÁLCULO E LÓGICA DA ANÁLISE (SEU CÓDIGO) ---
    # Garante que a coluna de data seja datetime para o cálculo dos dias
    df_pedido.set_index('created_at', inplace=True)

    # Vendas
    vendas_totais = df_itens['material_id'].value_counts().reset_index()
    vendas_totais.columns = ['material_id', 'total_vendido']
    num_dias = (df_pedido.index.max() - df_pedido.index.min()).days + 1
    vendas_totais['venda_media_diaria'] = vendas_totais['total_vendido'] / num_dias

    # Estoque
    df_estoque_total = df_supply.groupby(['material_id', 'material_name'])['quantity'].sum().reset_index()

    # Cobertura de Estoque
    df_cobertura = pd.merge(df_estoque_total, vendas_totais, on='material_id', how='left').fillna(0)
    df_cobertura['dias_de_estoque'] = np.where(
        df_cobertura['venda_media_diaria'] > 0,
        df_cobertura['quantity'] / df_cobertura['venda_media_diaria'],
        np.inf  # Estoque "infinito" se não há vendas
    )

    # Filtragem dos produtos críticos com base no slider
    # Itens com 0 dias de estoque, mas que também não tiveram vendas, são filtrados
    df_criticos = df_cobertura.query('dias_de_estoque> 0').sort_values('dias_de_estoque').head(X)

    # --- EXIBIÇÃO NA PÁGINA PRINCIPAL ---

    # 1. Alerta de Ruptura (Estoque Zerado)
    st.subheader("🚨 Alerta de Ruptura de Estoque")
    produtos_zerados = df_cobertura.query('dias_de_estoque == 0 and venda_media_diaria > 0')

    if not produtos_zerados.empty:
        st.warning(f"Encontrado(s) {len(produtos_zerados)} produto(s) com VENDA e ESTOQUE ZERADO!")
        with st.expander("Clique para ver os produtos com estoque zerado"):
            st.dataframe(produtos_zerados[['material_name', 'total_vendido', 'venda_media_diaria']], width='stretch')
    else:
        st.success("Ótima notícia! Nenhum produto com vendas ativas foi encontrado com estoque zerado.")

    st.write("---")

    # 2. Análise de Cobertura de Estoque
    st.markdown(f"""
        <div style="text-align: center; padding-top: 20px;">
            <p style="font-size: 40px; margin-bottom: 0;">Top {X} Produtos com Menor Cobertura de Estoque</p>
            <p style="font-size: 20px; margin-bottom: 0;">Estes são os produtos com maior risco de ruptura nos próximos dias, com base na sua venda média.</p>
    
        </div>
        """, unsafe_allow_html=True)
    
    _, a, _ = st.columns([1, 4, 1])
    with a:

        # Gráfico de Cobertura
        fig_cobertura, ax_cobertura = plt.subplots(figsize=(12, 8))
        sns.barplot(data=df_criticos, x='dias_de_estoque', y='material_name', ax=ax_cobertura)
        ax_cobertura.set_title(f'Top {X} Produtos com Estoque Mais Crítico (Cobertura Total)', fontsize=16, fontweight='bold')
        ax_cobertura.set_xlabel('Dias de Cobertura de Estoque', fontsize=12, fontweight='bold')
        ax_cobertura.set_ylabel('Produto', fontsize=12)
        ax_cobertura.bar_label(ax_cobertura.containers[0], fmt='%.1f dias', label_type='center', color='white', fontweight='bold')
        st.pyplot(fig_cobertura, width='stretch')

        # Tabela de dados de cobertura
        with st.expander(f"Clique para ver a tabela detalhada do Top {X} de itens críticos"):
            st.dataframe(
                df_criticos[['material_name', 'dias_de_estoque', 'quantity', 'total_vendido', 'venda_media_diaria']],
                width='stretch'
            )

        st.write("---")

        # 3. Análise de Distribuição do Estoque por Centro
        st.subheader(f"Distribuição do Estoque dos {X} Itens Mais Críticos por Centro")
        st.write("Este gráfico mostra onde o estoque dos itens mais críticos está localizado. Um estoque total pode parecer saudável, mas se estiver no centro de inventário errado, o risco de ruptura local é alto.")

        # Lógica para o gráfico de distribuição
        top_X_criticos_ids = df_criticos['material_id'].head(X)
        df_distribuicao_estoque = df_supply[df_supply['material_id'].isin(top_X_criticos_ids)]

        # Gráfico de Distribuição
        fig_dist, ax_dist = plt.subplots(figsize=(14, 8))
        sns.barplot(
            data=df_distribuicao_estoque,
            x='quantity',
            y='material_name',
            hue='inventory_centre_id',
            # dodge=False,  # Empilha as barras
            ax=ax_dist
        )
        ax_dist.set_title(f'Distribuição de Estoque dos {X} Itens Mais Críticos por Centro', fontsize=16, fontweight='bold')
        ax_dist.set_xlabel('Quantidade em Estoque', fontsize=12, fontweight='bold')
        ax_dist.set_ylabel('Produto', fontsize=12)
        ax_dist.legend(title='Centro de Inventário')
        st.pyplot(fig_dist, width='stretch')

        # Tabela de dados de distribuição
        with st.expander(f"Clique para ver a tabela detalhada da distribuição de estoque"):
            st.dataframe(
                df_distribuicao_estoque[['material_name', 'inventory_centre_id', 'quantity', 'material_id']],
                width='stretch'
        )

def page_analise_atraso(df_pedido, df_itens, df_supply):
    """Renderiza a página de análise de atrasos na entrega."""
    add_back_to_home_button()

    st.header("Análise de Atrasos na Entrega e Impacto do Estoque")
    st.write(
        "Esta página analisa a performance logística, identificando os estados e transportadoras com maiores taxas de atraso, "
        "e investiga a correlação entre os atrasos e a disponibilidade de estoque (ruptura ou estoque crítico)."
    )

    # --- PRÉ-PROCESSAMENTO E CÁLCULOS BASE ---
    coluna_prazo = 'Prazo a transportadora entregar no cliente'
    coluna_entrega = 'Entregue para o cliente em:'
    df_pedido[coluna_prazo] = pd.to_datetime(df_pedido[coluna_prazo], errors='coerce')
    df_pedido[coluna_entrega] = pd.to_datetime(df_pedido[coluna_entrega], errors='coerce')
    df_pedido_valido = df_pedido.dropna(subset=[coluna_prazo, coluna_entrega, 'created_at'])


    # --- CONTROLES INTERATIVOS NA BARRA LATERAL ---
    st.sidebar.header("Opções de Análise de Atraso")

    # Filtro de Estado
    estados_disponiveis = ['Todos os Estados'] + sorted(df_pedido_valido['Estado'].unique().tolist())
    estado_selecionado = st.sidebar.selectbox(
        "Selecione um Estado para análise detalhada:",
        options=estados_disponiveis
    )

    # Slider para Top X
    top_x = st.sidebar.slider(
        "Selecione o Top X para rankings de produtos:",
        min_value=3, max_value=20, value=5
    )
    
    # Slider para Limite de Estoque Crítico
    estoque_critico_limite = st.sidebar.slider(
        "Defina o limite para Estoque Crítico (unidades):",
        min_value=1, max_value=50, value=10
    )

    # Filtra o DataFrame principal com base na seleção
    if estado_selecionado != 'Todos os Estados':
        df_pedido_filtrado = df_pedido_valido[df_pedido_valido['Estado'] == estado_selecionado]
    else:
        df_pedido_filtrado = df_pedido_valido

    # --- SEÇÃO 1: ANÁLISE GERAL DE ATRASOS POR ESTADO ---
    st.subheader("Performance Logística por Estado")

    # Lógica de cálculo de atrasos
    df_pedido_atrasado = df_pedido_filtrado.query(f'`{coluna_entrega}` > `{coluna_prazo}`')
    total_pedidos_estado = df_pedido_filtrado['Estado'].value_counts()
    atrasados_por_estado = df_pedido_atrasado['Estado'].value_counts()

    df_analise_atrasos = pd.DataFrame({
        'Total de Pedidos': total_pedidos_estado,
        'Pedidos Atrasados': atrasados_por_estado
    }).fillna(0)
    df_analise_atrasos['Pedidos Atrasados'] = df_analise_atrasos['Pedidos Atrasados'].astype(int)
    
    df_analise_atrasos['Percentual de Atraso (%)'] = np.where(
        df_analise_atrasos['Total de Pedidos'] > 0,
        (df_analise_atrasos['Pedidos Atrasados'] / df_analise_atrasos['Total de Pedidos']) * 100,
        0
    )

    df_pedido_filtrado['Tempo de Entrega (dias)'] = (df_pedido_filtrado[coluna_entrega] - df_pedido_filtrado['created_at']).dt.days
    tempo_medio_entrega = df_pedido_filtrado.groupby('Estado')['Tempo de Entrega (dias)'].mean()
    df_analise_atrasos['Tempo Médio de Entrega (dias)'] = tempo_medio_entrega

    df_analise_atrasos = df_analise_atrasos.sort_values(by='Percentual de Atraso (%)', ascending=False)


    _, col0, _ = st.columns([1, 3, 1])
        
    with col0:
        fig_atraso_estado, ax_atraso_estado = plt.subplots(figsize=(10, 8))
        sns.barplot(y=df_analise_atrasos.index, x=df_analise_atrasos['Percentual de Atraso (%)'], ax=ax_atraso_estado)
        ax_atraso_estado.set_title('Percentual de Atraso por Estado', fontsize=16, fontweight='bold')
        ax_atraso_estado.set_xlabel('Percentual de Atraso (%)')
        ax_atraso_estado.set_ylabel('Estado')
        ax_atraso_estado.bar_label(ax_atraso_estado.containers[0], fmt='%.1f%%')
        st.pyplot(fig_atraso_estado, use_container_width=True)

    with st.expander("Clique para ver a tabela detalhada de performance por Estado"):
        st.dataframe(df_analise_atrasos.style.format({
            'Percentual de Atraso (%)': '{:.2f}%',
            'Tempo Médio de Entrega (dias)': '{:.1f}',
            'Pedidos Atrasados': '{:.0f}'
        }), use_container_width=True)

    st.write("---")

    # --- NOVA SEÇÃO: ANÁLISE POR TRANSPORTADORA ---
    st.subheader(f"Performance por Transportadora em '{estado_selecionado}'")

    # Lógica de cálculo por transportadora
    total_pedidos_transp = df_pedido_filtrado['Transportadora'].value_counts()
    atrasados_por_transp = df_pedido_atrasado['Transportadora'].value_counts()

    df_analise_transp = pd.DataFrame({
        'Total de Pedidos': total_pedidos_transp,
        'Pedidos Atrasados': atrasados_por_transp
    }).fillna(0)

    df_analise_transp['Pedidos Atrasados'] = df_analise_transp['Pedidos Atrasados'].astype(int)

    df_analise_transp['Percentual de Atraso (%)'] = np.where(
        df_analise_transp['Total de Pedidos'] > 0,
        (df_analise_transp['Pedidos Atrasados'] / df_analise_transp['Total de Pedidos']) * 100,
        0
    )

    _, col00, _ = st.columns([1, 3, 1])
    with col00:
        # Gráfico de Atraso por Transportadora
        fig_transp, ax_transp = plt.subplots(figsize=(12, 6))
        sns.barplot(y=df_analise_transp.index, x=df_analise_transp['Percentual de Atraso (%)'], ax=ax_transp)
        ax_transp.set_title(f"Percentual de Atraso por Transportadora em {estado_selecionado}", fontsize=16, fontweight='bold')
        ax_transp.set_xlabel('Percentual de Atraso (%)')
        ax_transp.set_ylabel('Transportadora')
        ax_transp.bar_label(ax_transp.containers[0], fmt='%.1f%%')
        st.pyplot(fig_transp, use_container_width=True)

    # Tabela detalhada por Estado/Transportadora se a visão for geral
    if estado_selecionado == 'Todos os Estados':
        with st.expander("Clique para ver a tabela detalhada de performance por Estado e Transportadora"):
            total_regional = df_pedido_filtrado.groupby(['Estado', 'Transportadora']).size()
            atrasados_regional = df_pedido_atrasado.groupby(['Estado', 'Transportadora']).size()
            df_analise_regional = pd.DataFrame({
                'Total de Pedidos': total_regional,
                'Pedidos Atrasados': atrasados_regional
            }).fillna(0)

            df_analise_regional['Pedidos Atrasados'] = df_analise_regional['Pedidos Atrasados'].astype(int)

            df_analise_regional['Percentual de Atraso (%)'] = (df_analise_regional['Pedidos Atrasados'] / df_analise_regional['Total de Pedidos'] * 100)
            st.dataframe(df_analise_regional.style.format({
                'Percentual de Atraso (%)': '{:.2f}%'}),
                # 'Pedidos Atrasados': '{:.0f}',
                use_container_width=True)
    else:
        with st.expander("Clique para ver a tabela detalhada de performance por Transportadora"):
            st.dataframe(df_analise_transp.style.format({'Percentual de Atraso (%)': '{:.2f}%'}), use_container_width=True)


    st.write("---")

    # --- SEÇÃO 3: CORRELAÇÃO ENTRE ATRASOS E ESTOQUE ---
    st.subheader(f"Análise da Relação entre Atrasos e Estoque em '{estado_selecionado}'")

    # Preparação dos dados de itens e estoque
    df_estoque_total = df_supply.groupby(['material_id', 'material_name'])['quantity'].sum().reset_index()
    ids_pedidos_atrasados = df_pedido_atrasado['id'].unique()
    df_financeiro_itens = df_itens[['order_id', 'material_name', 'material_id']]
    itens_atrasados = df_financeiro_itens[df_financeiro_itens['order_id'].isin(ids_pedidos_atrasados)]
    itens_atrasados_com_estoque = pd.merge(itens_atrasados, df_estoque_total, on=['material_id', 'material_name'], how='left').fillna(0)

    # Lógica de cálculo
    produtos_estoque_zerado = itens_atrasados_com_estoque[itens_atrasados_com_estoque['quantity'] == 0]
    produtos_estoque_critico = itens_atrasados_com_estoque[
        (itens_atrasados_com_estoque['quantity'] > 0) &
        (itens_atrasados_com_estoque['quantity'] <= estoque_critico_limite)
    ]

    total_itens_atrasados = len(itens_atrasados_com_estoque)
    qtd_zerado = len(produtos_estoque_zerado)
    qtd_critico = len(produtos_estoque_critico)
    
    perc_zerado = (qtd_zerado / total_itens_atrasados * 100) if total_itens_atrasados > 0 else 0
    perc_critico = (qtd_critico / total_itens_atrasados * 100) if total_itens_atrasados > 0 else 0

    # Exibição com st.metric
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Itens em Pedidos Atrasados com Estoque Zerado",
            value=f"{perc_zerado:.1f}%",
            help=f"{qtd_zerado} de {total_itens_atrasados} itens"
        )
    with col2:
        st.metric(
            label=f"Itens em Pedidos Atrasados com Estoque Crítico (≤ {estoque_critico_limite} un.)",
            value=f"{perc_critico:.1f}%",
            help=f"{qtd_critico} de {total_itens_atrasados} itens"
        )
        
    st.info("Estes cartões mostram a porcentagem de itens, dentro dos pedidos já atrasados, que também enfrentavam problemas de estoque no momento da análise.")

    # Tabelas de Top X produtos problemáticos
    col3, col4 = st.columns(2)
    with col3:
        st.write(f"**Top {top_x} Produtos com Estoque Zerado em Pedidos Atrasados**")
        df_top_zerado = produtos_estoque_zerado['material_name'].value_counts().head(top_x).reset_index()
        df_top_zerado.columns = ['Produto', 'Nº de Ocorrências em Atrasos']
        st.dataframe(df_top_zerado, use_container_width=True)

    with col4:
        st.write(f"**Top {top_x} Produtos com Estoque Crítico em Pedidos Atrasados**")
        df_top_critico = produtos_estoque_critico['material_name'].value_counts().head(top_x).reset_index()
        df_top_critico.columns = ['Produto', 'Nº de Ocorrências em Atrasos']
        st.dataframe(df_top_critico, use_container_width=True)


def render_home_page():
    
    st.markdown(f"""
<div style="text-align: center;">
    <p style="font-size: 50px; margin-bottom: 0;"><strong>Dashboard de Análise de Dados - Gocase Fev/2025</strong></p>
    <p style="font-size: 30px; margin-bottom: 0;"><strong>Este dashboard apresenta análises detalhadas sobre pedidos, descontos e faturamento. Navegue pelas seções abaixo para explorar os dados.</strong></p>
</div>
                
""", unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.info("📦 **Pedidos por Dia**")
        st.write("Visualize a distribuição de pedidos ao longo do tempo e identifique tendências diárias.")
        if st.button("Analisar Pedidos", key="nav_pedidos"):
            st.session_state.page = 'pedidos'
            st.rerun()

    with col2:
        st.info("💰 **Análise de Descontos**")
        st.write("Explore o impacto dos descontos e sua correlação com o número de vendas diárias.")
        if st.button("Analisar Descontos", key="nav_descontos"):
            st.session_state.page = 'descontos'
            st.rerun()

        
            
    with col3:
        st.info("📊 **Faturamento por Categoria e Produto**")
        st.write("Descubra quais categorias e produtos geram mais receita para o negócio.")
        if st.button("Analisar Faturamento", key="nav_faturamento"):
            st.session_state.page = 'faturamento'
            st.rerun()

    st.divider()

    col4, col5, col6 = st.columns(3, gap='large')

    with col4:
        st.info("❌ **Cancelamento de Pedidos**")
        st.write("Descubra quais categorias e produtos geram mais cancelamento para o negócio.")
        if st.button("Analisar Cancelamento", key="nav_cancelamento"):
            st.session_state.page = 'cancelamento'
            st.rerun()
    
    with col5:
        st.info("🏭 **Análise de Estoque**")
        st.write("Visualize o Estoque e descobra as Rupturas e Produtos Críticos.")
        if st.button("Analisar Estoque", key="nav_estoque"):
            st.session_state.page = 'estoque'
            st.rerun()
    
    with col6:
        st.info("⏰ **Análise de Atraso**")
        st.write("Visualize os Atrasos e Problemas Logísticos.")
        if st.button("Analisar Atraso", key="nav_atraso"):
            st.session_state.page = 'atraso'
            st.rerun()



df_pedido_original, df_itens_original, df_supply_original = load_data()

if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Roteador: Renderiza a página com base no estado
if st.session_state.page == 'home':
    render_home_page()
elif st.session_state.page == 'pedidos':
    page_pedidos_por_dia(df_pedido_original)
elif st.session_state.page == 'descontos':
    page_analise_descontos(df_pedido_original, df_itens_original)
elif st.session_state.page == 'faturamento':
    page_analise_faturamento(df_pedido_original, df_itens_original)
elif st.session_state.page == 'cancelamento':
    page_analise_cancelamento(df_pedido_original, df_itens_original, df_supply_original)
elif st.session_state.page == 'estoque':
    page_analise_estoque(df_pedido_original, df_itens_original, df_supply_original)
elif st.session_state.page == 'atraso':
    page_analise_atraso(df_pedido_original, df_itens_original, df_supply_original)