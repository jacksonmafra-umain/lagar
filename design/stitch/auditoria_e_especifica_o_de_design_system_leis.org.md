# Auditoria & Proposta de Design System — Leis.org (Mobile First)

## 1. Visão Geral Executiva & Diagnóstico do Sistema Atual
A auditoria técnica dos tokens em produção (`:root` e computed styles) do ecossistema **leis.org** revelou um conflito estrutural crítico entre dois sistemas paralelos de cores:
1. **Sistema Numérico Feito à Mão (`--primary-50...950`, `--secondary-50...950`)**
2. **Sistema Semântico Baseado no shadcn/ui (`--primary`, `--secondary`, `--muted`, `--accent`, `--border`, etc.)**

### Principais Falhas Identificadas
- **Desconexão de Tokens Semânticos**: Apenas `--primary` e `--secondary` estão vinculadas aos steps `500`. Tokens fundamentais como `--muted`, `--accent`, `--border` e `--input` possuem valores hardcoded padrão do Tailwind desvinculados da escala de cinzas calculada (`--secondary-50` vs `#f5f5f5`).
- **Violação Grave de Acessibilidade (WCAG 2.1 / 2.2)**:
  - `--primary-foreground` está fixo em `#fff` para todos os âmbitos. Em **Estaduais** (`#22be87`, contraste 2.39:1) e **Federais** (`#cfa65f`, contraste 2.26:1), botões com texto branco **reprovam veementemente no critério de AA** (mínimo 4.5:1).
  - Indicador de foco (`--ring`) a 2.52:1 viola o critério WCAG 2.2 SC 1.4.11 (mínimo 3.0:1) e conflitua com `--tw-ring-color: #3b82f680` (azul translúcido do Tailwind).
  - Texto de erro (`--destructive` com texto branco: 3.76:1) não atinge contraste de legibilidade.
  - No âmbito **Municipais**, a cor da marca (`#c41f2f`) dista apenas **2.1°** da cor de erro (`#ef4444`), impedindo que o usuário diferencie mensagens de erro de elementos institucionais da marca.
- **Hierarquia Tipográfica Monótona & Déficit de Leitura Legal**:
  - Tanto `--body-font` quanto `--heading-font` utilizam `Roboto`, com `line-height: 1.4` (22.4px em 16px). Isso é inadequado para o consumo de textos de lei densos, cheios de incisos, alíneas e parágrafos.
  - Falta suporte a numerais tabulares e falta de diferenciação entre a interface do app (*chrome*) e o texto da lei (*statute*).

---

## 2. Nova Arquitetura de Tokens Unificada (OKLCH & Sistema de Leitura)

### A. Tipografia Dupla Estruturada
- **Interface / Chrome do App**: `Inter, system-ui, sans-serif` (legibilidade em pequenos tamanhos, numerais tabulares alinhados para números de leis e artigos).
- **Corpo Legal / Estatutos**: `Source Serif 4, Georgia, serif` (ritmo vertical de leitura com `line-height: 1.65` e limite ótimo de largura `--measure-law: 68ch`).

### B. Escala Tipográfica Modular
- `--text-xs`: `0.75rem` (12px / 16px) — notas de rodapé, tags de status
- `--text-sm`: `0.875rem` (14px / 20px) — metadados, chips, labels auxiliares
- `--text-base`: `1rem` (16px / 24px) — padrão da interface mobile
- `--text-law`: `1.125rem` (18px / 30px, line-height 1.65) — leitura do texto dos artigos
- `--text-lg`: `1.25rem` (20px / 28px) — subtítulos de artigos e seções
- `--text-xl`: `1.5rem` (24px / 32px) — ementas de decretos / leis
- `--text-2xl`: `1.875rem` (30px / 36px) — cabeçalhos de tela

### C. Cores & Acessibilidade Resolvida por Âmbito (Contraste AAA/AA Garantido)
O token `--primary-foreground` agora é dinamicamente ajustado com base na luminosidade perceptiva (OKLCH L*):
1. **Municipais**:
   - `--primary`: `#b71c1c` (OKLCH equilibrado)
   - `--primary-foreground`: `#ffffff` (Contraste 6.4:1 ✓ AA)
   - Status de erro desacoplado: `#d92d20` com ícone obrigatório e borda diferenciada.
2. **Estaduais**:
   - `--primary`: `#1b7a54` (Verde esmeralda ajustado para contraste seguro)
   - `--primary-foreground`: `#ffffff` (Contraste 4.6:1 ✓ AA) ou base clara `#e8f7f0` com texto `#0b3824` (7.8:1 ✓ AAA)
3. **Federais**:
   - `--primary`: `#8a5a1e` (Dourado ocre profundo para botões preenchidos) ou fundo dourado claro com `--primary-foreground: #2a1b07` (Contraste 8.2:1 ✓ AAA)
4. **Institucionais**:
   - `--primary`: `#00008c`
   - `--primary-foreground`: `#ffffff` (Contraste 15.2:1 ✓ AAA)

### D. Superfícies Liquid Glass & Material You (M3 + Apple HIG)
- **Liquid Glass**:
  - `background: rgba(255, 255, 255, 0.78)`
  - `backdrop-filter: blur(20px) saturate(180%)`
  - `border: 1px solid rgba(255, 255, 255, 0.4)`
  - `box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.08)`
- **Interação & Foco (Compliance LBI / eMAG)**:
  - `--ring`: `#1e293b` (Contraste 11.2:1 contra o fundo) com anel duplo de 2px sólido e offset de 2px.
