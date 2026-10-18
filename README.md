# 🎯 Radar Julius - Caçador & Monitor de Preços

> *"Se você não comprar nada, o desconto é maior: é 100%!" — Julius Rock*

O **Radar Julius** é uma aplicação completa de inteligência de compras e web scraping de preços e promoções em tempo real. Desenvolvido para rastrear varejistas nacionais (**Mercado Livre, Amazon, Shopee, Magalu**) e redes de supermercados/atacados regionais (**Atacadão, Macromix, Super Rissul, Stock Center**).

---

## 🌟 Funcionalidades Principais

1. **Busca por Nicho ou Produto Específico:**
   - Varredura concorrente em múltiplos e-commerces e atacados.
   - Apresenta instantaneamente o **Top 5 Melhores Preços** com cálculo de economia potencial em R$.
2. **Top 3 Preços Históricos no Banco de Dados:**
   - Registra no PostgreSQL (Neon Cloud ou local) os **3 menores preços de todos os tempos** para cada produto monitorado, acompanhados da data/hora da captura e nome da loja.
3. **Monitoramento Contínuo com Alertas de Queda (>= X%):**
   - Serviço em background com agendador (APScheduler) para checagens periódicas automáticas.
   - Detecta reduções de preço que atingem a meta configurada (ex: queda >= 10%).
4. **Disparo de Notificações via n8n (WhatsApp & E-mail):**
   - Webhook integrado preparado para fluxos do **n8n**.
   - Gera payload estruturado com mensagens formatadas para WhatsApp (Evolution API / Z-API / Baileys) e templates HTML para nós de E-mail (SMTP / Resend / Gmail).
5. **Geolocalização Inteligente:**
   - Integração com ViaCEP para identificar a localidade do usuário e priorizar os supermercados e atacados da região (Grande Porto Alegre, Vale dos Sinos, RS, SC e Brasil).

---

## 🏗️ Estrutura do Projeto

```
Radar Julius/
├── app.py                      # Dashboard Interativo Streamlit
├── requirements.txt            # Dependências Python
├── .env.example                # Configurações de ambiente (Neon, n8n, etc.)
├── database/
│   ├── db.py                   # Conexão SQLAlchemy com Neon / Postgres local / SQLite
│   └── models.py               # Modelos: TrackedProduct, PriceCapture, HistoricalTopPrice, NotificationLog
├── scrapers/
│   ├── base.py                 # Interface base e modelo ProductItem
│   ├── manager.py              # Orquestrador de busca e consolidação Top 5
│   ├── retail/                 # Mercado Livre, Amazon, Magalu, Shopee
│   └── supermarkets/           # Atacadão, Macromix, Rissul, Stock Center
├── geo/
│   └── locator.py              # Consulta ViaCEP e mapeamento de redes locais
├── notifications/
│   └── n8n_dispatcher.py       # Disparador de Webhook com templates para n8n
└── services/
    └── monitor_service.py      # Serviço em background de verificação periódica
```

---

## 🚀 Como Executar

### 1. Instalar Dependências

Certifique-se de ter o Python 3.10+ instalado:

```powershell
py -m pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

Copie o `.env.example` para `.env` e configure conforme sua preferência:

```ini
# Para usar o Neon PostgreSQL na nuvem, cole a connection string do seu projeto Neon:
DATABASE_URL=postgresql://<usuario>:<senha>@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require

# Webhook do seu workflow no n8n:
N8N_WEBHOOK_URL=https://seu-n8n.exemplo.com/webhook/radar-julius-alert

# Intervalo padrão de checagem em minutos:
CHECK_INTERVAL_MINUTES=60
```

*Por padrão, o app roda imediatamente com SQLite local caso a URL do Neon não seja fornecida.*

### 3. Iniciar o Radar Julius

```powershell
cd "c:\Users\User\Documents\Cassio\Radar Julius"
py -m streamlit run app.py
```

O dashboard abrirá automaticamente no navegador em `http://localhost:8501`.

---

## ⚡ Conectando ao n8n

O Radar Julius envia um POST JSON para a `N8N_WEBHOOK_URL` com:
- `event`: `"PRICE_DROP_ALERT"`
- `product`: ID, nome e nicho do produto
- `pricing`: Loja, preço anterior, preço novo, desconto % e valor economizado
- `formatted_messages.whatsapp`: Texto pronto com negritos, emojis e link
- `formatted_messages.email_html`: Template HTML pronto para e-mail
- `julius_quote`: Frase marcante do Julius para engajar o usuário

